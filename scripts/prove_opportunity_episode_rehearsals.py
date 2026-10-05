"""Offline dense/gap physical sensitivity and frozen-writer rollback proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import types
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))
from scripts.prove_opportunity_episode_operability import START, forbid_external, peak_rss


def tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def physical(root: Path, size: int, gap: bool) -> dict:
    from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, nominate, synth_mint, token_object
    from solana_alpha_lab.factory.research_store import ResearchStore
    sys.addaudithook(forbid_external)
    sc = EpisodeScenario(root, start=START, stops=START + timedelta(hours=2))
    ResearchStore(root).prepare_write_lookup()
    mint = synth_mint("DenseSensitivity")
    def row(now):
        entropy = "".join(hashlib.sha256(f"{now.isoformat()}:{part}".encode()).hexdigest()
                          for part in range((size + 63)//64))[:size]
        return token_object(mint, price=1 + now.minute / 1000,
            liquidity=10000 + now.minute * 123, holders=60 + now.minute,
            extra={"vendorRich": entropy})
    sc.market.series[mint] = row
    nominate(sc.market, START, {"toporganicscore": [row(START)], "toptraded": [], "toptrending": []})
    if gap:
        sc.market.search_failures[START + timedelta(minutes=25)] = 429
    ticks = []
    for at in [START + timedelta(seconds=5)] + [START + timedelta(minutes=m, seconds=2)
              for m in range(10, 71, 5) if not (gap and m == 35)]:
        before = time.perf_counter()
        result = sc.tick(at)
        ticks.append({"wall_seconds": time.perf_counter()-before, "attempts": len(result["_calls"]),
                      "terminal": result.get("terminal"), "slot_states": result.get("slots_terminalized")})
        assert result["_exit_code"] == 0, result
    import pyarrow.parquet as pq
    observed = missing = rows_n = 0
    for path in (root / "datasets/parquet").rglob("observations.parquet"):
        for item in pq.read_table(path).to_pylist():
            rows_n += 1
            observed += item.get("state") == "OBSERVED"
            missing += item.get("state") != "OBSERVED"
    ops = sc.ops_path
    return {"mode": "GAP" if gap else "DENSE_OBSERVED", "rich_entropy_bytes_per_object": size,
            "sanitized_live_size_source": "UNAVAILABLE_SENSITIVITY_ONLY", "response_frozen_cap_bytes": 8*1024**2,
            "admissions": len(sc.admissions()), "observation_rows": rows_n, "observed": observed, "missing": missing,
            "peak_rss_bytes": peak_rss(), "ticks": ticks,
            "bytes": {"ops_db": ops.stat().st_size, "ops_wal": Path(str(ops)+"-wal").stat().st_size if Path(str(ops)+"-wal").exists() else 0,
              "raw_witness": tree_bytes(root / "datasets/raw_evidence"), "publications": tree_bytes(root / "datasets/parquet"),
              "research": tree_bytes(root / "research"), "manifests": tree_bytes(root / "datasets/manifests"),
              "total": tree_bytes(root)}}


def rollback(root: Path) -> dict:
    from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
    from tests.test_research_store import event_fixture
    base = "576e8c54715bb8af6b84877b91678ae659a42f88"
    raw = subprocess.check_output(["git", "show", f"{base}:src/solana_alpha_lab/factory/research_store.py"], cwd=ROOT)
    module = types.ModuleType("solana_alpha_lab.factory._frozen_rollback_store")
    module.__file__ = str(ROOT / "src/solana_alpha_lab/factory/research_store.py")
    sys.modules[module.__name__] = module
    exec(compile(raw, "frozen-research-store.py", "exec"), module.__dict__)
    store = ResearchStore(root)
    store.prepare_write_lookup()
    def event(name):
        return event_fixture(record_id=name, transaction_id=f"RESEARCH-TXN-{name}")
    store.append([event("NEW")], transaction_id="RESEARCH-TXN-NEW")
    old = module.ResearchStore(root)
    old.append([module.ResearchEvent.model_validate(event("OLD").model_dump())], transaction_id="RESEARCH-TXN-OLD")
    assert len(list(old.iter_committed_records())) == 2
    try:
        store.find_record("OLD")
    except ResearchStoreError as exc:
        refusal = exc.code
    else:
        raise AssertionError("ROLLBACK_WRITER_STALE_NOT_REFUSED")
    assert refusal == "WRITE_LOOKUP_STALE_PREPARATION_REQUIRED"
    store.prepare_write_lookup()
    assert store.find_record("OLD").record_id == "OLD"
    return {"frozen_base": base, "writer_blob_sha256": hashlib.sha256(raw).hexdigest(),
            "old_writer_append": "PASS", "old_readable_records": 2, "new_stale_refusal": refusal,
            "explicit_reprepare": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker-size", type=int)
    parser.add_argument("--gap", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.worker_size is not None:
        print(json.dumps(physical(root, args.worker_size, args.gap)))
        return 0
    if root.exists():
        raise RuntimeError("PROOF_ROOT_ALREADY_PRESENT")
    root.mkdir(parents=True)
    reports = []
    # Near the frozen 8MiB decoded-body cap, leave room for actual row structure.
    for size, gap in ((4096, False), (65536, False), (8*1024**2-2048, False), (4096, True)):
        child = subprocess.run([sys.executable, "-B", __file__, "--root", str(root / f"size-{size}-gap-{gap}"),
                                "--worker-size", str(size)] + (["--gap"] if gap else []),
                               text=True, capture_output=True, check=True)
        reports.append(json.loads(child.stdout.strip().splitlines()[-1]))
        (root / f"load-{size}-gap-{gap}.json").write_text(json.dumps(reports[-1], indent=2), encoding="utf-8")
    body = {"physical": reports, "rollback": rollback(root / "rollback")}
    (root / "report.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "loads": len(reports), "report": str(root / "report.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
