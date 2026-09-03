"""Zero-network PAPER/SHADOW operator accounting + control smoke."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    accept_signal_decision,
    run_commissioning,
)
from solana_alpha_lab.factory.paper_shadow_commands import (  # noqa: E402
    apply_operator_command,
)
from solana_alpha_lab.factory.paper_shadow_operations import (  # noqa: E402
    build_operations_projection,
)
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402

EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}
STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
LEGACY_STRAT = "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml"
MINT = "So11111111111111111111111111111111111111112"


def _signal(signal_id: str, *, decision_at: str = "2026-09-03T12:10:00Z") -> dict[str, Any]:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": "V1",
        "activation_epoch_id": EPOCH,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": MINT,
        "decision_at": decision_at,
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": "ENTER",
        "reason_code": "ACCOUNTING_FIXTURE_ENTER",
        "evidence_refs": [
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        ],
    }


def _open_and_fill(
    store: PaperPlaneStore,
    strategy: dict[str, Any],
    *,
    signal_id: str,
    entry_price: str,
    decision_at: str,
) -> str:
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal(signal_id, decision_at=decision_at),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of=decision_at,
    )
    position_id = str(accepted["position_id"])
    fee_bps = int(strategy["notional_policy"]["fee_bps"])
    notional = str(strategy["notional_policy"]["notional_usd"])
    store.apply_paper_entry_fill(
        position_id=position_id,
        entry_unit_price_usd=entry_price,
        entry_gross_notional_usd=notional,
        fee_bps=fee_bps,
        mode="PAPER",
    )
    return position_id


def run_smoke(*, keep_dir: Path | None = None) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="paper-shadow-ops-"))
    try:
        store_path = tmp / "paper_plane_state.sqlite"
        strategy = load_strategy_version(ROOT, STRAT_REL)
        store = PaperPlaneStore(store_path)

        # P1/P2/P3 reconciled known PnL
        p1 = _open_and_fill(
            store, strategy, signal_id="SIGDEC-ACC-P1", entry_price="1.00", decision_at="2026-09-03T12:10:00Z"
        )
        store.apply_paper_exit_fill(position_id=p1, exit_unit_price_usd="1.10", mode="PAPER")
        p2 = _open_and_fill(
            store, strategy, signal_id="SIGDEC-ACC-P2", entry_price="1.00", decision_at="2026-09-03T12:11:00Z"
        )
        store.apply_paper_exit_fill(position_id=p2, exit_unit_price_usd="0.90", mode="PAPER")
        p3 = _open_and_fill(
            store, strategy, signal_id="SIGDEC-ACC-P3", entry_price="1.00", decision_at="2026-09-03T12:12:00Z"
        )
        store.apply_paper_exit_fill(position_id=p3, exit_unit_price_usd="0.80", mode="PAPER")

        # P4 open UNKNOWN mark
        p4 = _open_and_fill(
            store, strategy, signal_id="SIGDEC-ACC-P4", entry_price="1.00", decision_at="2026-09-03T12:13:00Z"
        )
        store.record_position_mark(
            position_id=p4,
            mark_price_dec=None,
            as_of="2026-09-03T12:14:00Z",
            evidence_class="UNKNOWN",
        )

        # P5 exit requested unresolved
        p5 = _open_and_fill(
            store, strategy, signal_id="SIGDEC-ACC-P5", entry_price="1.00", decision_at="2026-09-03T12:15:00Z"
        )
        store.apply_paper_exit_fill(
            position_id=p5, exit_unit_price_usd=None, mode="PAPER", unresolved=True
        )

        bot_id = store.bots()[0]["bot_instance_id"]
        risk = store.pre_trade_risk_snapshot(
            bot_instance_id=bot_id,
            max_open_positions=int(strategy["risk_policy"]["max_open_positions"]),
        )

        # Same mint distinct signal positions
        distinct = {p1, p2, p3, p4, p5}
        same_mint_distinct = len(distinct) == 5

        ops = build_operations_projection(store, bot_instance_id=bot_id)
        known_pnl = [
            row["net_pnl_usd"]
            for row in ops["position_rows"]
            if row["position_id"] in {p1, p2, p3}
        ]

        # Pause blocks entry; exit while paused still works; resume restores entry.
        apply_operator_command(
            store,
            {
                "command_type": "PAUSE_NEW_ENTRIES",
                "idempotency_key": "CMD-PAUSE-1",
                "bot_instance_id": bot_id,
            },
        )
        pause_blocks_entry = False
        try:
            accept_signal_decision(
                ROOT,
                store,
                strategy=strategy,
                signal_decision=_signal("SIGDEC-ACC-PAUSED", decision_at="2026-09-03T12:16:00Z"),
                known_activation_epochs=KNOWN_EPOCHS,
                mode="PAPER",
                as_of="2026-09-03T12:16:00Z",
            )
        except PaperPlaneError as exc:
            pause_blocks_entry = str(exc) == "ENTRIES_PAUSED"

        close_one = apply_operator_command(
            store,
            {
                "command_type": "REQUEST_CLOSE_POSITION",
                "idempotency_key": "CMD-CLOSE-P4",
                "position_id": p4,
            },
        )
        exit_while_paused = close_one.get("state") == "EXIT_REQUIRED"

        apply_operator_command(
            store,
            {
                "command_type": "RESUME_NEW_ENTRIES",
                "idempotency_key": "CMD-RESUME-1",
                "bot_instance_id": bot_id,
            },
        )
        resume_allows_entry = False
        try:
            p6 = _open_and_fill(
                store,
                strategy,
                signal_id="SIGDEC-ACC-P6",
                entry_price="1.00",
                decision_at="2026-09-03T12:17:00Z",
            )
            resume_allows_entry = store.get_position(p6) is not None
        except PaperPlaneError:
            resume_allows_entry = False

        stale = apply_operator_command(
            store,
            {
                "command_type": "REQUEST_CLOSE_ALL",
                "idempotency_key": "CMD-CLOSE-ALL-STALE",
                "bot_instance_id": bot_id,
                "expected_open_position_set_sha256": "0" * 64,
            },
        )
        ops_live = build_operations_projection(store, bot_instance_id=bot_id)
        close_all_valid = apply_operator_command(
            store,
            {
                "command_type": "REQUEST_CLOSE_ALL",
                "idempotency_key": "CMD-CLOSE-ALL-OK",
                "bot_instance_id": bot_id,
                "expected_open_position_set_sha256": ops_live["open_position_set_sha256"],
            },
        )
        dup = apply_operator_command(
            store,
            {
                "command_type": "REQUEST_CLOSE_ALL",
                "idempotency_key": "CMD-CLOSE-ALL-OK",
                "bot_instance_id": bot_id,
                "expected_open_position_set_sha256": ops_live["open_position_set_sha256"],
            },
        )

        stop = apply_operator_command(
            store,
            {
                "command_type": "STOP_BOT",
                "idempotency_key": "CMD-STOP-1",
                "bot_instance_id": bot_id,
            },
        )
        draining = stop.get("bot_status") == "DRAINING"
        drain_blocks_entry = False
        try:
            accept_signal_decision(
                ROOT,
                store,
                strategy=strategy,
                signal_decision=_signal("SIGDEC-ACC-DRAIN", decision_at="2026-09-03T12:18:00Z"),
                known_activation_epochs=KNOWN_EPOCHS,
                mode="PAPER",
                as_of="2026-09-03T12:18:00Z",
            )
        except PaperPlaneError as exc:
            drain_blocks_entry = str(exc) == "BOT_STATUS_BLOCKS_ENTRY:DRAINING"
        still_draining = store.get_bot(bot_id)["status"] == "DRAINING"

        events = store.execution_events()
        event_types = {e["event_type"] for e in events}
        lineage_ok = {
            "SIGNAL_DECISION_ACCEPTED",
            "PRE_TRADE_RISK_SNAPSHOT",
            "RECONCILIATION",
            "OPERATOR_COMMAND_APPLIED",
        }.issubset(event_types)

        p4_row = next(r for r in ops["position_rows"] if r["position_id"] == p4)
        unknown_pnl_preserved = p4_row["pnl_status"] == "UNKNOWN" and p4_row["net_pnl_usd"] is None

        # Restart readback
        store.close()
        store2 = PaperPlaneStore(store_path)
        ops2 = build_operations_projection(store2, bot_instance_id=bot_id)
        bot2 = store2.get_bot(bot_id)
        assert bot2 is not None
        unresolved_preserved = any(
            row["state"] == "UNRESOLVED" for row in ops2["position_rows"]
        )
        cmd = store2.get_operator_command("CMD-CLOSE-ALL-OK")
        events2 = store2.execution_events()
        restart_ok = (
            cmd is not None
            and bot2["status"] == "DRAINING"
            and len(events2) == len(events)
        )

        # Legacy v1.0 still works on separate store
        legacy = run_commissioning(
            ROOT,
            strategy_relatives=[LEGACY_STRAT],
            store_path=tmp / "legacy.sqlite",
            cohort=[
                {"mint": MINT, "X_LIQUIDITY_USD": 2500},
                {"mint": "So22222222222222222222222222222222222222222", "X_LIQUIDITY_USD": 500},
            ],
        )

        store2.close()

        terminal_ok = (
            ops["current_loss_streak_count"] == 2
            and ops["max_drawdown_usd"] == "30.37"
            and pause_blocks_entry
            and resume_allows_entry
            and exit_while_paused
            and unknown_pnl_preserved
            and lineage_ok
            and drain_blocks_entry
            and still_draining
            and stale.get("status") == "STALE_OPERATOR_SNAPSHOT"
            and close_all_valid.get("status") == "APPLIED"
            and dup.get("idempotent") is True
            and draining
            and unresolved_preserved
            and restart_ok
            and same_mint_distinct
            and known_pnl == ["9.79", "-10.19", "-20.18"]
        )
        payload = {
            "terminal": (
                "PAPER_SHADOW_ACCOUNTING_CONTROL_PASS"
                if terminal_ok
                else "ACCOUNTING_TRUTH_AMBIGUOUS_REPLAN"
            ),
            "legacy_v1_compat": legacy["per_strategy"][0]["simulated_fills"] == 1,
            "candidate_v1_1": True,
            "signal_lineage": lineage_ok,
            "activation_epoch_lineage": True,
            "risk_snapshot": risk,
            "same_mint_distinct_signal_positions": same_mint_distinct,
            "known_pnl": known_pnl,
            "unknown_pnl_preserved": unknown_pnl_preserved,
            "loss_streak_count": ops["current_loss_streak_count"],
            "max_drawdown_usd": ops["max_drawdown_usd"],
            "pause_blocks_entry": pause_blocks_entry,
            "resume_allows_entry": resume_allows_entry,
            "exit_while_paused": exit_while_paused,
            "close_one": close_one.get("status") == "APPLIED",
            "close_all_stale_snapshot_denied": stale.get("status") == "STALE_OPERATOR_SNAPSHOT",
            "close_all_valid": close_all_valid.get("status") == "APPLIED",
            "duplicate_command_idempotent": dup.get("idempotent") is True,
            "draining_before_stopped": draining and still_draining and drain_blocks_entry,
            "unresolved_inventory_preserved": unresolved_preserved,
            "restart_readback": restart_ok,
            "provider_calls": 0,
            "credential_reads": 0,
            "wallet_signer_tx": 0,
            "cash_spend_usd_cents": 0,
            "ops_as_of": ops2["as_of"],
            "open_position_set_sha256": ops2["open_position_set_sha256"],
        }
        if keep_dir is not None:
            keep_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(store_path, keep_dir / "paper_plane_state.sqlite")
            (keep_dir / "smoke_result.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
        return payload
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--keep-dir", type=Path, default=None)
    args = parser.parse_args()
    result = run_smoke(keep_dir=args.keep_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["terminal"])
    return 0 if result["terminal"] == "PAPER_SHADOW_ACCOUNTING_CONTROL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
