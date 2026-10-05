"""Offline real-tick history falsifier. Setup is never included in tick timing.

Only HTTP and clock use the existing complete physical fixture. No publisher,
lease, lifecycle, filesystem read or ResearchStore implementation is replaced.
Instrumentation calls the original operations and observes their work.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

START = datetime(2026, 10, 5, tzinfo=UTC)


def peak_rss() -> int:
    if os.name != "nt":
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise RuntimeError("RSS_MEASUREMENT_FAILED")
    return int(counters.PeakWorkingSetSize)


def forbid_external(event, args):
    if event == "subprocess.Popen" and args[1] in (["git", "rev-parse", "HEAD"], "git rev-parse HEAD"):
        return
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
        raise RuntimeError("FIXTURE_EXTERNAL_ACCESS_FORBIDDEN")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        name = str(args[0]).replace("\\", "/").lower()
        if "/.ssh/" in name or name.endswith((".env", "secrets.env")):
            raise RuntimeError("FIXTURE_SECRET_ACCESS_FORBIDDEN")


def materialize_history(root: Path, count: int, size: int) -> dict:
    """Linear setup with canonical serializers, followed by real validation.

    Unique high-entropy payloads avoid the identical-JSON compression illusion.
    This is valid irrelevant research history, not a claimed dense trajectory.
    """
    from solana_alpha_lab.factory.research_store import ResearchStore, _prepare_records
    from solana_alpha_lab.storage.manifests import canonical_manifest_bytes
    from tests.test_research_store import event_fixture
    store = ResearchStore(root)
    started = time.perf_counter()
    for index in range(count):
        txn = f"RESEARCH-TXN-HISTORY-{index:08d}"
        blob = "".join(hashlib.sha256(f"{index}:{part}".encode()).hexdigest()
                       for part in range((size + 63) // 64))[:size]
        records = _prepare_records([event_fixture(
            record_id=f"HISTORY-{index:08d}", transaction_id=txn,
            record_kind="OBSERVATION_BATCH",
            payload={"fixture": "VALID_DIVERSE_HISTORY", "number": index,
                     "schedule_sha256": hashlib.sha256(f"retired-{index//864}".encode()).hexdigest(),
                     "activation_id": f"ACT-RETIRED-{index//864}",
                     "population": "OPPORTUNITY_EPISODES",
                     "rows": [{"mint": f"SynthRetired{index:08d}" + "1" * 20,
                               "usdPrice": 1 + index / 10000, "liquidity": 5000 + index,
                               "holderCount": 50 + index % 1000,
                               "stats5m": {"buyVolume": index * 1.2345,
                                           "sellVolume": index * 0.753}}],
                     "vendor_rich_metadata": blob})], transaction_id=txn)
        parquet, observed = store._stage_parquet(records)
        manifest = store._build_manifest(transaction_id=txn, records=observed, parquet_bytes=parquet)
        data = root / manifest.logical_location
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_bytes(parquet)
        target = root / "research/manifests/partitions" / f"{manifest.partition_manifest_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical_manifest_bytes(manifest))
    assert sum(1 for _ in store.iter_committed_records()) >= count
    return {"setup_seconds": time.perf_counter() - started, "setup_peak_rss_bytes": peak_rss(), "history_transactions": count,
            "payload_size": size, "validated": True}


def measure_tick(root: Path, mode: str, work_minute: int = 10) -> dict:
    from solana_alpha_lab.factory.research_store import ResearchStore
    from tests.test_opportunity_episodes_harness_v1 import (
        SyntheticMarket, cli_tick, cli_command, nominate, synth_mint, token_object)
    sys.addaudithook(forbid_external)
    market = SyntheticMarket()
    mint = synth_mint("Operability")
    market.series[mint] = lambda at: token_object(mint, price=1.0 + at.minute / 1000,
                                                liquidity=10000, holders=60 + at.minute)
    nominate(market, START, {"toporganicscore": [market.series[mint](START)],
                             "toptraded": [], "toptrending": []})
    at = START + {"admit": timedelta(seconds=5), "normal": timedelta(minutes=work_minute, seconds=2),
                  "restart": timedelta(minutes=work_minute, seconds=40), "status": timedelta(minutes=work_minute, seconds=45)}[mode]
    counters = {"manifest_headers": 0, "partition_opens": 0, "partition_bytes": 0,
                "records_decoded": 0, "path_reads": 0, "path_bytes": 0,
                "appends": 0, "append_seconds": 0., "inventory_seconds": 0.,
                "duplicate_lookup_seconds": 0., "lock_seconds": 0.}
    original_read = Path.read_bytes
    original_manifest = ResearchStore._read_manifest
    original_verify = ResearchStore._verify_partition
    original_append = ResearchStore.append
    original_inventory = ResearchStore._committed_manifests
    original_lookup = ResearchStore._existing_transaction
    original_lease = ResearchStore.writer_lease
    try:
        from solana_alpha_lab.factory.research_write_lookup import WriteLookup
        original_bounded_read = getattr(WriteLookup, "_read_bytes", None)
    except ModuleNotFoundError as exc:
        if exc.name != "solana_alpha_lab.factory.research_write_lookup":
            raise
        WriteLookup = None  # frozen predecessor has no prepared lookup

    def bounded_read(lookup, name):
        result = original_bounded_read(lookup, name)
        counters["path_reads"] += 1
        counters["path_bytes"] += len(result)
        return result

    def read(path):
        result = original_read(path)
        counters["path_reads"] += 1
        counters["path_bytes"] += len(result)
        return result
    def manifest(store, path):
        counters["manifest_headers"] += 1
        return original_manifest(store, path)
    def verify(store, item):
        counters["partition_opens"] += 1
        counters["partition_bytes"] += (root / item.logical_location).stat().st_size
        result = original_verify(store, item)
        counters["records_decoded"] += len(result)
        return result
    def timed(method, key, count=None):
        def call(*args, **kwargs):
            before = time.perf_counter()
            if count:
                counters[count] += 1
            try:
                return method(*args, **kwargs)
            finally:
                counters[key] += time.perf_counter() - before
        return call
    @contextlib.contextmanager
    def lease(store):
        with original_lease(store):
            before = time.perf_counter()
            try:
                yield
            finally:
                counters["lock_seconds"] += time.perf_counter() - before

    with contextlib.ExitStack() as stack:
        if WriteLookup is not None and original_bounded_read is not None:
            stack.enter_context(patch.object(WriteLookup, "_read_bytes", bounded_read))
        for owner, name, replacement in (
            (Path, "read_bytes", read), (ResearchStore, "_read_manifest", manifest),
            (ResearchStore, "_verify_partition", verify),
            (ResearchStore, "append", timed(original_append, "append_seconds", "appends")),
            (ResearchStore, "_committed_manifests", timed(original_inventory, "inventory_seconds")),
            (ResearchStore, "_existing_transaction", timed(original_lookup, "duplicate_lookup_seconds")),
            (ResearchStore, "writer_lease", lease)):
            stack.enter_context(patch.object(owner, name, replacement))
        before = time.perf_counter()
        result = cli_command(root, at, "status") if mode == "status" else cli_tick(root, market, at)
        wall = time.perf_counter() - before
    assert result["_exit_code"] == 0, result
    return {"mode": mode, "wall_seconds": wall, "peak_rss_bytes": peak_rss(),
            "terminal": result.get("terminal"), "publications": len(result.get("publications", [])),
            "synthetic_provider_attempts": len(result.get("_calls", [])), **counters}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--counts", default="0,32,128")
    parser.add_argument("--payload-size", type=int, default=4096)
    parser.add_argument("--prepared", action="store_true")
    parser.add_argument("--enforce-limits", action="store_true")
    parser.add_argument("--worker", choices=["admit", "normal", "restart", "status"])
    parser.add_argument("--work-minute", type=int, default=10)
    args = parser.parse_args()
    args.root = args.root.resolve()
    if args.worker:
        print(json.dumps(measure_tick(args.root, args.worker, args.work_minute), sort_keys=True))
        return 0
    from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario
    args.root.mkdir(parents=True, exist_ok=True)
    reports = []
    for count in map(int, args.counts.split(",")):
        root = args.root / f"history-{count}-{args.payload_size}"
        if root.exists():
            raise RuntimeError("PROOF_ROOT_ALREADY_PRESENT")
        EpisodeScenario(root, start=START, stops=START + timedelta(hours=1))
        setup = materialize_history(root, count, args.payload_size)
        if args.prepared:
            from solana_alpha_lab.factory.research_store import ResearchStore
            before = time.perf_counter()
            setup["preparation"] = ResearchStore(root).prepare_write_lookup()
            setup["preparation_seconds"] = time.perf_counter() - before
            setup["preparation_peak_rss_bytes"] = peak_rss()
        for mode in ("admit", "normal", "restart", "status"):
            started = time.perf_counter()
            child = subprocess.run([sys.executable, "-B", __file__, "--root", str(root),
                                    "--worker", mode], capture_output=True, text=True, check=True)
            report = json.loads(child.stdout.strip().splitlines()[-1])
            report.update(setup, process_seconds=time.perf_counter() - started)
            if args.enforce_limits:
                assert report["wall_seconds"] < 30, "LOCAL_TICK_WALL_CEILING"
                assert report["peak_rss_bytes"] < 512 * 1024**2, "LOCAL_TICK_MEMORY_CEILING"
                assert report["inventory_seconds"] == 0, "FULL_MANIFEST_INVENTORY"
                assert report["partition_opens"] <= 7, "UNRELATED_PAYLOAD_HISTORY_SCAN"
            reports.append(report)
            print(json.dumps(report, sort_keys=True), flush=True)
    (args.root / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
