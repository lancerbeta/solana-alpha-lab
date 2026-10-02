"""Offline fixture/resource probe; run each consumer in a fresh process."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
DIGEST = "a" * 64
ACTIVATION = "PROFILE"
RECENT = "PRIM-JUPITER-TOKENS-V2-RECENT-001"


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


def create_fixture(root: Path, old_rows: int, payload_bytes: int) -> dict[str, object]:
    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    path = (root / "store.sqlite3").resolve()
    store = ObservationScheduleStore(path)
    stamp = "2026-10-02T11:59:00Z"
    store.upsert_activation({
        "schedule_sha256": DIGEST, "activation_id": ACTIVATION,
        "schedule_key": "PROFILE", "state": "ACTIVE",
        "starts_at": "2026-10-01T00:00:00Z", "stops_admitting_at": "2026-10-05T13:00:00Z",
        "payload": {"last_tick_at": stamp},
    }, clock=NOW)
    payload = json.dumps({"schedule_sha256": DIGEST, "activation_id": ACTIVATION,
                          "http_class": "HTTP_OK", "status": "OBSERVED",
                          "historical_response": "x" * payload_bytes})
    store._conn.executemany(
        "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ((f"r{i}", f"c{i}", f"a{i}", "COMPLETED", RECENT, payload,
          "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z") for i in range(old_rows)),
    )
    recent_payload = json.dumps({"schedule_sha256": DIGEST, "activation_id": ACTIVATION,
                                 "http_class": "HTTP_OK", "status": "OBSERVED",
                                 "response": "r" * 1024})
    store._conn.executemany(
        "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ((f"rr{i}", f"cc{i}", f"aa{i}", "COMPLETED", RECENT, recent_payload, stamp, stamp)
         for i in range(128)),
    )
    small = json.dumps({"note": "x" * 2048})
    store._conn.executemany("INSERT INTO candidate_members VALUES (?, ?, ?, ?, ?, ?, ?)",
        ((DIGEST, ACTIVATION, f"e{i:08}", "MEMBER", small, stamp, stamp) for i in range(6000)))
    store._conn.executemany("INSERT INTO due_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ((DIGEST, ACTIVATION, f"e{i:08}", "X1", RECENT, "OBSERVED", stamp, stamp,
          None, None, small, stamp, stamp) for i in range(12000)))
    store._conn.commit()
    store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.close()
    rdp = root / "rdp"
    rdp.mkdir(parents=True, exist_ok=True)
    for i in range(2500):
        (rdp / f"fixture-{i:05}.bin").write_bytes(b"r" * 1024)
    return {"old_call_rows": old_rows, "recent_call_rows": 128,
            "old_payload_bytes_per_row": len(payload.encode()), "sqlite_bytes": path.stat().st_size,
            "candidate_rows": 6000, "due_rows": 12000, "rdp_files": 2500, "rdp_bytes": 2500 * 1024}


def measure(root: Path, consumer: str) -> dict[str, object]:
    from solana_alpha_lab.factory.observation_schedule_store import (
        ObservationScheduleStore, reset_store_read_stats, store_read_stats,
    )
    from solana_alpha_lab.factory.collector_read_model import build_collector_read_model
    from solana_alpha_lab.factory.collector_operational_packet import build_collector_operational_packet
    from solana_alpha_lab.factory.operability_watch import evaluate_operability
    from solana_alpha_lab.factory.collector_owner_pulse import run_daily_owner_pulse

    store = ObservationScheduleStore((root / "store.sqlite3").resolve(), readonly=True)
    reset_store_read_stats()
    legacy_counts = {"call_ledger_rows_returned": 0, "call_payloads_decoded": 0}
    original = store.list_calls

    def observed_list_calls(**kwargs):
        rows = original(**kwargs)
        legacy_counts["call_ledger_rows_returned"] += len(rows)
        legacy_counts["call_payloads_decoded"] += len(rows)
        return rows

    store.list_calls = observed_list_calls
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
        result = evaluate_operability(**common, emit=False, persist=False)
        summary = {"verdict": result["packet_verdict"], "message_chars": sum(map(len, result["preview_messages"]))}
    elif consumer == "pulse":
        result = run_daily_owner_pulse(**common, mode="dry-run")
        summary = {"observations_24h": result["packet"]["observations_24h"], "message_chars": len(result["text"])}
    else:
        raise ValueError(consumer)
    wall = time.perf_counter() - started
    stats = store_read_stats()
    store.close()
    return {"consumer": consumer, "wall_seconds": round(wall, 6), "peak_rss_bytes": peak_rss_bytes(),
            "legacy_call_read": legacy_counts, "store_read_stats": stats, "result": summary,
            "measurement": "fresh process; OS lifetime peak working set/RSS; timed complete consumer; no network"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("create", "measure"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--old-rows", type=int, default=2048)
    parser.add_argument("--payload-bytes", type=int, default=65536)
    parser.add_argument("--consumer", choices=("read_model", "packet", "watch", "pulse"))
    args = parser.parse_args()
    result = create_fixture(args.root, args.old_rows, args.payload_bytes) if args.mode == "create" else measure(args.root, args.consumer)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
