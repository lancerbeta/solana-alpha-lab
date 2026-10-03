"""Offline fixture/resource probe; run each consumer in a fresh process."""

from __future__ import annotations

import argparse
import ast
import ctypes
import io
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
ACTIVATION = "PROFILE"
RECENT = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
BASE = "94b284534b6ad55a95002d51b9d04b4a5ced6bde"


def peak_rss_bytes() -> int:
    if os.name != "nt":
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)


def create_fixture(root: Path, old_rows: int, payload_bytes: int, recent_rows: int = 128) -> dict[str, object]:
    root = root.resolve()
    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
    from solana_alpha_lab.factory.observation_schedule import canonical_sha256, parse_utc, render_utc, validate_observation_schedule
    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        _authority_policy, _research_event, activate_schedule, activation_transition_research_event_proven,
        authorize_schedule,
        expected_authority_phrase, register_schedule,
    )
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore
    from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

    path = root / "store.sqlite"
    store = ObservationScheduleStore(path)
    stamp = "2026-10-02T11:59:00Z"
    document = yaml.safe_load((ROOT / "tests/fixtures/observation_schedule/x300_y900.yaml").read_text(encoding="utf-8"))
    document["activation"]["starts_at"] = "2026-10-02T00:00:00Z"
    document["activation"]["stops_admitting_at"] = "2026-10-03T00:00:00Z"
    document = validate_observation_schedule(document, root=ROOT)
    digest = str(document["schedule_sha256"])
    rdp = root / "rdp"
    rdp.mkdir(parents=True, exist_ok=True)
    event_time = datetime(2026, 10, 2, 0, 10, tzinfo=UTC)
    registered = register_schedule(root=ROOT, data_root=rdp, store=store,
                                   document=document, now=event_time, producer_git_sha="c" * 40)
    assert registered["schedule_sha256"] == digest
    horizon = max(int(point["due_offset_seconds"]) + int(point["allowed_lateness_seconds"])
                  for point in [document["x_point"], *document["y_points"]])
    expires = render_utc(parse_utc(document["activation"]["stops_admitting_at"]) + timedelta(seconds=horizon))
    policy = _authority_policy(root=ROOT, document=document, schedule_key=document["schedule_key"], expires_at=expires)
    phrase = expected_authority_phrase(
        schedule_sha256=digest, schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=policy["provider_route_ids"], expires_at=expires,
        policy_digest=canonical_sha256(policy),
    )
    authorize_schedule(root=ROOT, data_root=rdp, store=store, schedule_sha256=digest,
                       phrase=phrase, now=event_time, producer_git_sha="c" * 40)
    activate_schedule(root=ROOT, data_root=rdp, store=store, schedule_sha256=digest,
                      activation_id=ACTIVATION, now=event_time, producer_git_sha="c" * 40)
    transition_proven = activation_transition_research_event_proven(
        rdp, store.get_activation(digest, ACTIVATION), now=NOW,
    )
    if not transition_proven:
        raise RuntimeError("FIXTURE_IMMUTABLE_PROOF_FAILED")
    # Real old Parquet+manifest pairs, produced by the normal serializers. Their
    # payloads must not be opened by the report's lifecycle proof route.
    research = ResearchStore(rdp)
    for i in range(max(1, old_rows // 64)):
        member = i % 2 == 0
        transaction = (f"RESEARCH-TXN-MEM-PROFILE-HISTORY-{i:06}" if member
                       else f"RESEARCH-TXN-PROFILE-HISTORY-{i:06}")
        event = _research_event(
            record_id=f"PROFILE-HISTORY-{i:06}",
            record_kind=RecordKind.OBSERVATION_MEMBER_BATCH if member else RecordKind.RESEARCH_ARTIFACT,
            entity_id="f" * 64 if member else f"PROFILE-HISTORY-{i:06}",
            payload={"synthetic_history": "x" * 16384, "schedule_sha256": "f" * 64,
                     "batch_id": f"PROFILE-HISTORY-{i:06}"},
            now=datetime(2026, 9, 1, tzinfo=UTC), producer_git_sha="c" * 40,
            run_id="ACT-PROFILE-HISTORY" if member else None, transaction_id=transaction,
        )
        parquet, records = research._stage_parquet([event])
        manifest = research._build_manifest(transaction_id=transaction, records=records, parquet_bytes=parquet)
        parquet_path = rdp / manifest.logical_location
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        parquet_path.write_bytes(parquet)
        (rdp / "research/manifests/partitions" / f"{manifest.partition_manifest_id}.json").write_bytes(
            canonical_manifest_bytes(manifest))
    payload = json.dumps({"schedule_sha256": digest, "activation_id": ACTIVATION,
                          "http_class": "HTTP_OK", "status": "OBSERVED",
                          "historical_response": "x" * payload_bytes})
    store._conn.executemany(
        "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ((f"r{i}", f"c{i}", f"a{i}", "COMPLETED", RECENT, payload,
          "2026-09-01T00:00:00Z", ("2026-09-01T00:00:00Z",
          "2026-09-01T00:00:00,123Z", "2026-09-01T00:00:00.Z")[i % 3]) for i in range(old_rows)),
    )
    recent_payload = json.dumps({"schedule_sha256": digest, "activation_id": ACTIVATION,
                                 "http_class": "HTTP_OK", "status": "OBSERVED",
                                 "response": "r" * 1024})
    store._conn.executemany(
        "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ((f"rr{i}", f"cc{i}", f"aa{i}", "COMPLETED", RECENT, recent_payload, stamp, stamp)
         for i in range(recent_rows)),
    )
    small = json.dumps({"note": "x" * 2048})
    store._conn.executemany("INSERT INTO candidate_members VALUES (?, ?, ?, ?, ?, ?, ?)",
        ((digest, ACTIVATION, f"e{i:08}", "MEMBER", small, stamp, stamp) for i in range(6000)))
    store._conn.executemany("INSERT INTO due_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ((digest, ACTIVATION, f"e{i:08}", "X1", RECENT, "OBSERVED", stamp, stamp,
          None, None, small, stamp, stamp) for i in range(12000)))
    store._conn.commit()
    store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.close()
    for i in range(2500):
        (rdp / f"fixture-{i:05}.bin").write_bytes(b"r" * 1024)
    manifest_count = len(tuple((rdp / "research/manifests/partitions").glob("*.json")))
    # Existing direct packet tests may use an OS temporary directory. Real CLI
    # probes use a fixture under repo/local so the normal safe-relative runtime
    # config loader is exercised without changing a production CLI.
    if root.is_relative_to(ROOT):
        runtime = yaml.safe_load((ROOT / "configs/observation_schedule_runtime_v1.yaml").read_text(encoding="utf-8"))
        runtime["ops_store_relative"] = path.relative_to(ROOT).as_posix()
        runtime["data_root"] = rdp.relative_to(ROOT).as_posix()
        runtime["producer_git_sha"] = "c" * 40
        (root / "runtime.yaml").write_text(yaml.safe_dump(runtime), encoding="utf-8")
    fixture = {"old_call_rows": old_rows, "recent_call_rows": recent_rows,
            "old_payload_bytes_per_row": len(payload.encode()), "sqlite_bytes": path.stat().st_size,
            "candidate_rows": 6000, "due_rows": 12000, "rdp_files": 2500,
            "rdp_bytes": 2500 * 1024, "immutable_manifests": manifest_count,
            "activation_transition_proven": transition_proven}
    (root / "fixture.json").write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
    return fixture


def measure(root: Path, consumer: str, *, baseline: bool = False) -> dict[str, object]:
    root = root.resolve()
    from solana_alpha_lab.factory.observation_schedule_store import (
        ObservationScheduleStore, reset_store_read_stats, store_read_stats,
    )
    from solana_alpha_lab.factory.collector_read_model import build_collector_read_model
    from solana_alpha_lab.factory.collector_operational_packet import build_collector_operational_packet
    from solana_alpha_lab.factory import collector_operational_packet as packet_module
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory import observation_schedule_store as store_module

    original_bounded = ResearchStore.iter_lifecycle_records_bounded

    if baseline:
        # Execute only the exact frozen-base query method. All other consumer
        # inputs are identical; disable the new per-packet reuse as well.
        source = subprocess.check_output(
            ["git", "show", f"{BASE}:src/solana_alpha_lab/factory/observation_schedule_store.py"],
            cwd=ROOT, text=True)
        klass = next(node for node in ast.parse(source).body
                     if isinstance(node, ast.ClassDef) and node.name == "ObservationScheduleStore")
        method = next(node for node in klass.body
                      if isinstance(node, ast.FunctionDef) and node.name == "iter_operability_calls")
        namespace = dict(store_module.__dict__)
        exec(compile(ast.Module(body=[method], type_ignores=[]), "frozen_base_query", "exec"), namespace)
        ObservationScheduleStore.iter_operability_calls = namespace[method.name]
        from solana_alpha_lab.factory import operability_watch, collector_owner_pulse
        uncached = packet_module.build_collector_operational_packet.__wrapped__
        operability_watch.build_collector_operational_packet = uncached
        collector_owner_pulse.build_collector_operational_packet = uncached
        def legacy_predecessor(self, **kwargs):
            kwargs["include_member_predecessor"] = True
            return original_bounded(self, **kwargs)
        ResearchStore.iter_lifecycle_records_bounded = legacy_predecessor

    reset_store_read_stats()
    legacy_counts = {"call_ledger_rows_returned": 0, "call_payloads_decoded": 0}
    store = ObservationScheduleStore(root / "store.sqlite", readonly=True)
    original = ObservationScheduleStore.list_calls

    def observed_list_calls(self, **kwargs):
        rows = original(self, **kwargs)
        legacy_counts["call_ledger_rows_returned"] += len(rows)
        legacy_counts["call_payloads_decoded"] += len(rows)
        return rows

    ObservationScheduleStore.list_calls = observed_list_calls
    observed = {"manifest_reads": 0, "partition_verifications": 0, "old_member_payload_reads": 0}
    original_manifest = ResearchStore._read_manifest
    original_partition = ResearchStore._verify_partition
    original_model = packet_module.build_collector_read_model
    model_summary = {}

    def read_manifest(self, path):
        observed["manifest_reads"] += 1
        return original_manifest(self, path)

    def verify_partition(self, manifest):
        observed["partition_verifications"] += 1
        if "PROFILE-HISTORY" in manifest.partition_id:
            observed["old_member_payload_reads"] += 1
            if not baseline:
                raise RuntimeError("IRRELEVANT_HISTORY_PAYLOAD_OPENED")
        return original_partition(self, manifest)

    def read_model(*args, **kwargs):
        result = original_model(*args, **kwargs)
        model_summary.update({key: result[key] for key in ("observations_24h", "call_diagnostics_status")})
        return result

    ResearchStore._read_manifest = read_manifest
    ResearchStore._verify_partition = verify_partition
    packet_module.build_collector_read_model = read_model
    common = dict(root=root, store=store, now=NOW, observation_rdp=root / "rdp",
                  remote_config={}, environ={})
    started = time.perf_counter()
    if consumer == "read_model":
        result = build_collector_read_model(store, now=NOW)
        summary = {"observations_24h": result["observations_24h"]}
    elif consumer == "packet":
        result = build_collector_operational_packet(**common)
        summary = {"observations_24h": result["observations_24h"], "verdict": result["collector_verdict"]}
    elif consumer == "watch":
        from scripts.factory_operability_watch import main as watch_main
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = watch_main(["--mode", "dry-run", "--skip-systemd", "--now",
                                    NOW.isoformat().replace("+00:00", "Z"), "--runtime-config",
                                    (root / "runtime.yaml").relative_to(ROOT).as_posix()])
        result = json.loads(output.getvalue())
        summary = {"verdict": result["packet_verdict"], "cli_exit": exit_code,
                   "message_chars": sum(map(len, result["preview_messages"]))}
    elif consumer == "pulse":
        from scripts.collector_owner_pulse import main as pulse_main
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = pulse_main(["--mode", "dry-run", "--json", "--now",
                                    NOW.isoformat().replace("+00:00", "Z"), "--runtime-config",
                                    (root / "runtime.yaml").relative_to(ROOT).as_posix()])
        decoder = json.JSONDecoder()
        first, end = decoder.raw_decode(output.getvalue())
        packet = decoder.raw_decode(output.getvalue()[end:].lstrip())[0]["packet"]
        summary = {"observations_24h": packet["observations_24h"],
                   "call_diagnostics_status": packet["call_diagnostics_status"],
                   "cli_exit": exit_code, "message_chars": len(first["text"])}
    else:
        raise ValueError(consumer)
    wall = time.perf_counter() - started
    stats = store_read_stats()
    ObservationScheduleStore.list_calls = original
    ResearchStore._read_manifest = original_manifest
    ResearchStore._verify_partition = original_partition
    ResearchStore.iter_lifecycle_records_bounded = original_bounded
    packet_module.build_collector_read_model = original_model
    summary.update(model_summary)
    store.close()
    return {"consumer": consumer, "baseline": baseline, "wall_seconds": round(wall, 6), "peak_rss_bytes": peak_rss_bytes(),
            "legacy_call_read": legacy_counts, "store_read_stats": stats, "result": summary,
            "immutable_reads": observed,
            "measurement": "fresh process; OS lifetime peak working set/RSS; timed complete consumer; no network"}


def cgroup_gate(root: Path, consumer: str, *, baseline: bool = False) -> dict[str, object]:
    """Linux CI gate using the same oneshot cap as Factory report services."""
    if sys.platform != "linux":
        raise RuntimeError("LINUX_CGROUP_REQUIRED")
    root = root.resolve()
    root.relative_to(ROOT / "local")  # cache eviction is restricted to the synthetic fixture
    fixture = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
    recent_rows = int(fixture.get("recent_call_rows", 128))
    # Flush synthetic files before advisory eviction. This is a preparation
    # policy, not a claim that actual cache residency has been measured.
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
                os.posix_fadvise(handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    unit = f"factory-resource-proof-{consumer}-{uuid.uuid4().hex[:8]}"
    command = [
        "sudo", "systemd-run", f"--unit={unit}", "--service-type=oneshot",
        "--remain-after-exit", "--property=MemoryAccounting=yes",
        "--property=MemoryMax=768M", "--property=TimeoutStartSec=180s",
        "--property=PrivateNetwork=yes", "--property=RestrictAddressFamilies=AF_UNIX",
        f"--property=WorkingDirectory={ROOT}",
        "--property=NoNewPrivileges=yes", sys.executable, "-B",
        str(Path(__file__).resolve()), "measure", "--root", str(root.resolve()),
        "--consumer", consumer,
    ]
    if baseline:
        command.append("--baseline")
    try:
        launch = subprocess.run(command, capture_output=True, text=True, timeout=210,
                                check=False)
        deadline = time.monotonic() + 195
        while True:
            state = subprocess.run(
                ["sudo", "systemctl", "show", f"{unit}.service", "--no-pager",
                 "-p", "Result", "-p", "ExecMainStatus", "-p", "MemoryPeak",
                 "-p", "MemoryMax", "-p", "ExecMainStartTimestampMonotonic",
                 "-p", "ExecMainExitTimestampMonotonic", "-p", "ActiveState", "-p", "SubState"],
                capture_output=True, text=True, timeout=10, check=False)
            fields = dict(line.split("=", 1) for line in state.stdout.splitlines() if "=" in line)
            if state.returncode or fields.get("SubState") not in ("running", "start", "start-pre", "start-post"):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(1)
        journal = subprocess.run(
            ["sudo", "journalctl", "-u", f"{unit}.service", "-o", "cat",
             "--no-pager", "-n", "30"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        measured = [json.loads(line) for line in journal.stdout.splitlines()
                    if line.startswith("{") and '"consumer"' in line]
        peak = int(fields.get("MemoryPeak") or 0)
        start = int(fields.get("ExecMainStartTimestampMonotonic") or 0)
        end = int(fields.get("ExecMainExitTimestampMonotonic") or 0)
        wall = (end - start) / 1_000_000 if end > start > 0 else None
        completed = (
            launch.returncode == state.returncode == journal.returncode == 0
            and fields.get("Result") == "success"
            and fields.get("ActiveState") == "active"
            and fields.get("SubState") == "exited"
            and fields.get("ExecMainStatus") == "0"
            and fields.get("MemoryMax") == str(768 * 1024 * 1024)
            and 0 < peak <= 768 * 1024 * 1024
            and wall is not None and 0 < wall < 180
            and len(measured) == 1 and measured[0].get("consumer") == consumer
            and measured[0].get("baseline") is baseline
            and measured[0].get("store_read_stats", {}).get(
                "call_diagnostics_rows_returned") == recent_rows
            and measured[0].get("result", {}).get("cli_exit") == 0
            and measured[0]["result"].get("observations_24h") == recent_rows
            and measured[0]["result"].get("call_diagnostics_status") == "EXACT"
            and measured[0].get("immutable_reads", {}).get("partition_verifications", 0) > 0
        )
        stats = measured[0].get("store_read_stats", {}) if len(measured) == 1 else {}
        read_bound = stats.get("call_diagnostics_index_candidates") == recent_rows and stats.get(
            "call_diagnostics_payload_projections") == recent_rows
        reuse_proven = len(measured) == 1 and measured[0].get("immutable_reads", {}).get(
            "manifest_reads") == fixture["immutable_manifests"]
        baseline_reproduced = (stats.get("call_ledger_timestamp_rows_examined") == fixture["old_call_rows"] + recent_rows
                               and measured[0].get("immutable_reads", {}).get("old_member_payload_reads", 0) > 0)
        baseline_exhausted = (
            baseline and launch.returncode in (0, 1) and state.returncode == journal.returncode == 0
            and fields.get("MemoryMax") == str(768 * 1024 * 1024)
            and fields.get("ActiveState") == "failed" and fields.get("SubState") == "failed"
            and 0 < peak <= 768 * 1024 * 1024 and wall is not None and 0 < wall <= 195
            and ((fields.get("Result") == "oom-kill" and peak >= 512 * 1024 * 1024)
                 or (fields.get("Result") == "timeout" and wall >= 175))
        )
        success = ((completed and baseline_reproduced) or baseline_exhausted) if baseline else (
            completed and read_bound and reuse_proven and peak < 512 * 1024 * 1024 and wall < 120)
        return {"consumer": consumer, "baseline": baseline, "pass": success,
                "fixture": fixture, "fixture_cache_eviction": "FSYNC_AND_ADVISORY_DONTNEED",
                "cache_residency_verified": False,
                "memory_peak_bytes": peak or None, "wall_seconds": wall,
                "memory_max_bytes": int(fields.get("MemoryMax") or 0) or None,
                "legacy_timestamp_udf_evaluations": stats.get("call_ledger_timestamp_rows_examined"),
                "index_candidates_returned": stats.get("call_diagnostics_index_candidates"),
                "consumer_measurement": measured[0] if len(measured) == 1 else None,
                "baseline_resource_falsifier": "RESOURCE_EXHAUSTED" if baseline_exhausted else None,
                "result": fields.get("Result") or "UNKNOWN",
                "launch_exit": launch.returncode}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"consumer": consumer, "baseline": baseline, "pass": False,
                "result": "RESOURCE_PROOF_UNAVAILABLE"}
    finally:
        subprocess.run(["sudo", "systemctl", "stop", f"{unit}.service"],
                       capture_output=True, timeout=10, check=False)


def cgroup_suite(root: Path) -> dict[str, object]:
    """Growing-history vertical loop, every consumer in a fresh cgroup."""
    runs = []
    for rows in (16384, 32768):
        fixture_root = root / str(rows)
        create_fixture(fixture_root, rows, 32768, recent_rows=1162)
        # Exercise explicit migration on a populated synthetic copy, not only
        # index maintenance while filling an empty new database.
        import sqlite3
        from scripts.factory_prepare_operability_index import prepare
        with sqlite3.connect(fixture_root.resolve() / "store.sqlite") as connection:
            connection.execute("DROP INDEX idx_call_ledger_operability_time")
        migration = prepare(fixture_root.resolve() / "store.sqlite")
        print(json.dumps({"migration": migration, "old_rows": rows}, sort_keys=True), flush=True)
        for baseline, consumer in ((True, "watch"), (False, "watch"), (False, "pulse")):
            run = cgroup_gate(fixture_root, consumer, baseline=baseline)
            runs.append(run)
            print(json.dumps(run, sort_keys=True), flush=True)
    scalable = all(run.get("pass") is True for run in runs)
    if scalable:
        for consumer in ("watch", "pulse"):
            first, second = [run for run in runs if run["consumer"] == consumer and not run["baseline"]]
            scalable = scalable and (
                second["memory_peak_bytes"] <= first["memory_peak_bytes"] * 1.25 + 8 * 1024**2
                and second["wall_seconds"] <= first["wall_seconds"] * 1.5 + 1)
    return {"pass": scalable, "proof": "GROWING_HISTORY_CGROUP_REAL_CLI",
            "history_rows": [16384, 32768], "recent_rows_fixed": 1162,
            "old_parquet_payload_opened": False,
            "limitation": "manifest headers enumerated once per packet; no historical call scan or old Parquet payload read"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("create", "measure", "cgroup-gate", "cgroup-suite"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--old-rows", type=int, default=2048)
    parser.add_argument("--payload-bytes", type=int, default=65536)
    parser.add_argument("--consumer", choices=("read_model", "packet", "watch", "pulse"))
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if args.mode == "create":
        result = create_fixture(args.root, args.old_rows, args.payload_bytes)
    elif args.mode == "measure":
        result = measure(args.root, args.consumer, baseline=args.baseline)
    elif args.mode == "cgroup-gate":
        result = cgroup_gate(args.root, args.consumer, baseline=args.baseline)
    else:
        result = cgroup_suite(args.root)
    print(json.dumps(result, sort_keys=True))
    if args.mode in ("cgroup-gate", "cgroup-suite") and not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
