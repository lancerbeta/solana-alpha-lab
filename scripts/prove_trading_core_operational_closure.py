"""Compact synthetic process boundary for native operational closure proofs.

This is a test harness, not an alternative trading coordinator. It drives the
production run method and replaces only clocks and the lowest quote transport.
Every synthetic effect lives in a separate durable ledger outside runtime backup.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import hashlib
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner
from solana_alpha_lab.factory.trading_coordinator import TradingCoordinator, exact_child
from solana_alpha_lab.factory.trading_adapters import JupiterQuoteAdapter, ENDPOINT
from solana_alpha_lab.factory.hfic_research_scope import sha256_of
from solana_alpha_lab.factory.observation_schedule import parse_utc


def peak_rss_bytes():
    if os.name == "nt":
        import ctypes
        class Counters(ctypes.Structure):
            _fields_=[("cb",ctypes.c_ulong),("faults",ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in
                ("peak_working_set","working_set","peak_paged","paged","peak_nonpaged","nonpaged","pagefile","peak_pagefile")]
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        counter=Counters()
        counter.cb=ctypes.sizeof(counter)
        kernel.K32GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if not kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counter),counter.cb):
            raise ValueError("RSS_MEASUREMENT_UNAVAILABLE")
        return int(counter.peak_working_set)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=="darwin" else 1024)


def suite_main(argv):
    parser=argparse.ArgumentParser(description="Isolated native closure suite and compact execution receipt")
    parser.add_argument("--suite",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(ROOT/"tests"))
    modules=["test_trading_core_operational_closure_v1","test_trading_operational_adapters_v1",
             "test_trading_operational_obligations_v1","test_trading_operational_recovery_v1","test_trading_continuity_v1"]
    source_paths=["src/solana_alpha_lab/factory/"+name+".py" for name in
        ("trading_coordinator","trading_runner","trading_adapters","episode_decision","paper_plane","trading_runtime_policy","risk_economics","paper_shadow_commands","observation_schedule_store")]
    source_paths += ["scripts/trading_continuity.py","scripts/prove_trading_core_operational_closure.py"]
    source_paths += ["tests/"+name+".py" for name in modules]
    before_pins={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths}
    class Results(unittest.TextTestResult):
        def startTest(self,test):
            self.started=time.perf_counter()
            super().startTest(test)
        def stopTest(self,test):
            owned=getattr(test,"tmp",None) or getattr(test,"_tmp",None)
            cleaned=owned is None or not Path(owned.name).exists()
            records.append({"test":test.id(),"duration_seconds":round(time.perf_counter()-self.started,6),
                "owned_root_absent":cleaned,"metrics":getattr(test,"metrics",{})})
            super().stopTest(test)
    records=[]
    started=time.perf_counter()
    suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
    result=unittest.TextTestRunner(verbosity=1,resultclass=Results).run(suite)
    # Exact source pins, no machine paths, exception text or sensitive dumps.
    after_pins={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths}
    receipt={"schema":"smial.operating-software-proof","schema_version":"1.0",
        "status":"PASS" if result.wasSuccessful() and before_pins==after_pins and all(row["owned_root_absent"] for row in records) else "FAIL",
        "code_unchanged_during_execution":before_pins==after_pins,
        "tests_run":result.testsRun,"failed_test_ids":[test.id() for test,_ in result.failures+result.errors],
        "elapsed_seconds":round(time.perf_counter()-started,6),"peak_rss_bytes":peak_rss_bytes(),
        "evidence_class":"SYNTHETIC_OFFLINE","provider_calls":False,"credential_reads":False,"live_authority":False,
        "source_pins":before_pins,"tests":records}
    receipt["receipt_sha256"]=sha256_of(receipt)
    output=exact_child(ROOT,args.output.absolute().relative_to(ROOT),exists=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({key:receipt[key] for key in ("status","tests_run","elapsed_seconds","peak_rss_bytes","receipt_sha256")}))
    return 0 if receipt["status"]=="PASS" else 1


class RecordingQuoteAdapter(JupiterQuoteAdapter):
    """Context wrapper; quote economics/parser always remain production-owned."""
    def __init__(self, ledger, plan):
        self.ledger, self.plan = ledger, plan
        self.context = None
        super().__init__(timeout_seconds=1, max_response_bytes=8192, transport=self.wire_transport)

    def wire_transport(self, raw, **limits):
        if limits["api_key"] is not None or set(raw) != {"inputMint", "outputMint", "amount"}:
            raise AssertionError("SYNTHETIC_BOUNDARY_AUTHORITY_ESCAPE")
        database = sqlite3.connect(self.ledger)
        try:
            database.execute("CREATE TABLE IF NOT EXISTS calls(call_id INTEGER PRIMARY KEY,attempt_id TEXT NOT NULL,receipt_json TEXT)")
            index = database.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            entry = self.plan[min(index, len(self.plan) - 1)]
            cursor = database.execute("INSERT INTO calls(attempt_id) VALUES(?)", (self.context[0]["attempt_id"],))
            self.call_id = cursor.lastrowid
            database.commit()
        finally:
            database.close()
        body = {"transaction": None, **raw, "inAmount": raw["amount"],
            "outAmount": entry.get("outAmount", "10000000000000"), "router": "metis", "mode": "ultra",
            "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "SYNTHETIC-" + str(index)}
        body.pop("amount")
        return {"status": entry.get("status", 200), "body": json.dumps(body).encode(),
                "url": ENDPOINT + "?" + urlencode(raw)}

    def dispatch(self, attempt, request, *, as_of):
        self.context = (attempt, request)
        result, proof = super().dispatch(attempt, request, as_of=as_of)
        receipt = {"attempt": attempt, "request": request, "result": result}
        receipt["receipt_sha256"] = sha256_of(receipt)
        database = sqlite3.connect(self.ledger)
        try:
            database.execute("UPDATE calls SET receipt_json=? WHERE call_id=?", (json.dumps(receipt, sort_keys=True), self.call_id))
            database.commit()
        finally:
            database.close()
        return result, proof


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if "--suite" in argv:
        return suite_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("PAPER", "SHADOW"), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--fault")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--ticks", type=int, default=1)
    args = parser.parse_args(argv)
    runner = TradingContinuityRunner(args.repository_root, data_root=args.data_root)
    # The runner's strict synthetic marker/root guard is mandatory here.
    if not (runner.data_root / "offline_runtime.json").is_file():
        raise ValueError("SYNTHETIC_PROOF_ROOT_REQUIRED")
    def fault(point):
        if point == args.fault:
            sentinel = exact_child(runner.data_root, "fault-reached.json", exists=False)
            with sentinel.open("w", encoding="utf-8") as file:
                json.dump({"point": point}, file)
                file.flush()
                os.fsync(file.fileno())
            while True:
                time.sleep(.05)  # Parent terminates the real process here.
    adapter = None
    if args.mode == "SHADOW":
        if args.ledger is None or args.plan is None:
            raise ValueError("EXACT_SYNTHETIC_LEDGER_AND_PLAN_REQUIRED")
        owned = (args.repository_root / "local").resolve(strict=True)
        ledger = exact_child(owned, args.ledger.absolute().relative_to(owned), exists=False)
        plan = exact_child(owned, args.plan.absolute().relative_to(owned))
        adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text(encoding="utf-8")))
    coordinator = TradingCoordinator(runner, mode=args.mode, clock=lambda: parse_utc(args.as_of), quote_adapter=adapter, fault=fault)
    result=coordinator.run(ticks=args.ticks)
    print(json.dumps({**result,"peak_rss_bytes":peak_rss_bytes()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
