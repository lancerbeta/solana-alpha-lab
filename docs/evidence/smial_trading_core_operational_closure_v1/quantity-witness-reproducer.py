"""Bounded packet-only ARCH P1 falsifier; no network, only owned native fixtures."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
import subprocess
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]
import hashlib
import json
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from tests.test_trading_core_operational_closure_v1 import OperatingDriverTests
from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
from solana_alpha_lab.factory.paper_plane import (
    PaperPlaneStore, accept_signal_decision_outcome, assert_quantity_inventory_witness,
)
from solana_alpha_lab.factory.trading_runtime_policy import obligation_summary
from solana_alpha_lab.factory.hfic_research_scope import sha256_of

SCRATCH = ROOT / "local/smial-quantity-witness-native-fixtures"
SCRATCH.mkdir(exist_ok=False)
SCRATCH_MARKER = SCRATCH / "architecture-owner.json"
SCRATCH_MARKER.write_text(json.dumps({"owner": "ARCHITECTURE_CRITIC", "head": HEAD}), encoding="utf-8")
tempfile.tempdir = str(SCRATCH)

def run_case(damage):
    case = OperatingDriverTests()
    case.setUp()
    owned = case.root.parent
    (owned / "architecture-owner.json").write_text(json.dumps({"owner": "ARCHITECTURE_CRITIC", "head": HEAD}), encoding="utf-8")
    try:
        case.start_operating(mode="SHADOW")
        packet = case.runner.episode(source_relative="source/observation_schedule_state.sqlite",
            episode_id=case.source.admissions()[0]["episode_id"], epoch_id=case.epoch,
            mode="SHADOW", as_of="2026-10-05T12:40:00Z")
        with closing(PaperPlaneStore(case.runner.store_path)) as store:
            admitted = accept_signal_decision_outcome(case.root, store, strategy=case.runner.strategy,
                signal_decision=packet["decision"], known_activation_epochs={case.epoch},
                mode="SHADOW", as_of="2026-10-05T12:40:00Z")
            pid = admitted["position_id"]
            original = store.apply_paper_entry_fill(position_id=pid, entry_unit_price_usd="0.000003",
                entry_gross_notional_usd="30", fee_bps=20, mode="SHADOW")
            assert_quantity_inventory_witness(store, original)
            original_journal = store.filtered_execution_events(position_ids=[pid])
            before_attempts = len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[pid]))
            if damage:
                store._conn.execute("UPDATE positions SET qty_dec=NULL,remaining_qty_dec='1000000',remaining_cost_basis_usd_dec='3',remaining_entry_fee_usd_dec='0.006' WHERE position_id=?", (pid,))
            damaged_journal = store.filtered_execution_events(position_ids=[pid])
            witness = "RETURNED_WITHOUT_ERROR"
            try:
                assert_quantity_inventory_witness(store, store.get_position(pid))
            except Exception as error:
                witness = type(error).__name__ + ":" + str(error)
            before_inventory = obligation_summary(store, mode="SHADOW")
        case.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        case.now = datetime(2026,10,5,13,10,tzinfo=UTC)
        ledger, plan = case.wire_files([{"outAmount": "330000000"}])
        case.quote_inputs(at="2026-10-05T13:10:00Z")
        case.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        run = case.coordinator.run(ticks=1)
        wire = case.ledger_receipts(ledger) if ledger.exists() else []
        with closing(PaperPlaneStore(case.runner.store_path, readonly=True)) as store:
            final = store.get_position(pid)
            after_inventory = obligation_summary(store, mode="SHADOW")
            facts = {"case": "NULL_ORIGINAL_QTY_WITH_FORGED_REMAINDER" if damage else "INTACT_CONTROL",
                "original_native_quantity": original["qty_dec"], "original_journal_sha256": sha256_of(original_journal),
                "damage_preserved_original_journal": original_journal == damaged_journal,
                "inventory_verifier": witness, "before_inventory_status": before_inventory["inventory_status"],
                "before_known_floor_usd": before_inventory["known_cost_basis_floor_usd"],
                "attempts_before": before_attempts,
                "attempts_after": len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[pid])),
                "requests_after": len(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND", position_ids=[pid])),
                "captures_after": len(store.filtered_execution_events(event_type="ADAPTER_RESULT_CAPTURED", position_ids=[pid])),
                "accepted_results_after": len(store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED", position_ids=[pid])),
                "finals_after": len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_FINAL", position_ids=[pid])),
                "synthetic_quote_calls": len(wire), "wire_raw_amount": wire[0]["request"]["amount"] if wire else None,
                "wire_remaining_quantity": wire[0]["request"]["remaining_quantity"] if wire else None,
                "state_after": final["state"], "after_inventory_status": after_inventory["inventory_status"], "run": run}
    finally:
        case.tearDown()
    facts["owned_fixture_absent"] = not owned.exists()
    return facts

try:
    report = {"head": HEAD, "source_basis": "WORKTREE_SOURCE_SHA256", "real_provider_calls": 0,
        "credential_reads": 0, "full_gate": "NOT_EXECUTED", "source_pins": {
            name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                "src/solana_alpha_lab/factory/paper_plane.py", "src/solana_alpha_lab/factory/trading_coordinator.py",
                "tests/test_trading_core_operational_closure_v1.py")}, "cases": [run_case(False), run_case(True)]}
finally:
    SCRATCH_MARKER.unlink()
    SCRATCH.rmdir()
report["owned_scratch_absent"] = not SCRATCH.exists()
print(json.dumps(report, sort_keys=True, ensure_ascii=True))
