"""PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1 focused acceptance suite."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    accept_signal_decision,
)
from solana_alpha_lab.factory.paper_shadow_commands import (  # noqa: E402
    apply_operator_command,
    maybe_finish_drain,
)
from solana_alpha_lab.factory.paper_shadow_operations import (  # noqa: E402
    build_operations_projection,
    compute_loss_streak,
    compute_max_drawdown_usd,
)
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "paper_shadow_accounting_control"
STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}
MINT = "So11111111111111111111111111111111111111112"


def _signal(signal_id: str, *, decision_at: str = "2026-09-03T12:10:00Z") -> dict:
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


def _open_filled(store: PaperPlaneStore, strategy: dict, signal_id: str, decision_at: str) -> str:
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal(signal_id, decision_at=decision_at),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of=decision_at,
    )
    pid = str(accepted["position_id"])
    store.apply_paper_entry_fill(
        position_id=pid,
        entry_unit_price_usd="1.00",
        entry_gross_notional_usd=str(strategy["notional_policy"]["notional_usd"]),
        fee_bps=int(strategy["notional_policy"]["fee_bps"]),
        mode="PAPER",
    )
    return pid


class PaperShadowAccountingControlTests(unittest.TestCase):
    def test_decimal_fixture_pnl_streak_drawdown(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                p1 = _open_filled(store, strategy, "SIGDEC-T-P1", "2026-09-03T12:10:00Z")
                store.apply_paper_exit_fill(position_id=p1, exit_unit_price_usd="1.10", mode="PAPER")
                p2 = _open_filled(store, strategy, "SIGDEC-T-P2", "2026-09-03T12:11:00Z")
                store.apply_paper_exit_fill(position_id=p2, exit_unit_price_usd="0.90", mode="PAPER")
                p3 = _open_filled(store, strategy, "SIGDEC-T-P3", "2026-09-03T12:12:00Z")
                store.apply_paper_exit_fill(position_id=p3, exit_unit_price_usd="0.80", mode="PAPER")
                p4 = _open_filled(store, strategy, "SIGDEC-T-P4", "2026-09-03T12:13:00Z")
                store.record_position_mark(
                    position_id=p4,
                    mark_price_dec=None,
                    as_of="2026-09-03T12:14:00Z",
                    evidence_class="UNKNOWN",
                )
                p5 = _open_filled(store, strategy, "SIGDEC-T-P5", "2026-09-03T12:15:00Z")
                store.apply_paper_exit_fill(
                    position_id=p5, exit_unit_price_usd=None, mode="PAPER", unresolved=True
                )
                ops = build_operations_projection(store)
                self.assertEqual(ops["current_loss_streak_count"], 2)
                self.assertEqual(ops["max_drawdown_usd"], "30.37")
                by_id = {r["position_id"]: r for r in ops["position_rows"]}
                self.assertEqual(by_id[p1]["net_pnl_usd"], "9.79")
                self.assertEqual(by_id[p2]["net_pnl_usd"], "-10.19")
                self.assertEqual(by_id[p3]["net_pnl_usd"], "-20.18")
                self.assertEqual(by_id[p4]["pnl_status"], "UNKNOWN")
                self.assertIsNone(by_id[p4]["net_pnl_usd"])
                self.assertEqual(by_id[p5]["state"], "UNRESOLVED")
                self.assertEqual(by_id[p1]["pnl_evidence_class"], "PAPER_RECONCILED_MODEL")
                self.assertEqual(ops["reconciled_net_pnl_status"], "KNOWN")
                self.assertEqual(ops["max_drawdown_status"], "KNOWN")
                self.assertEqual(ops["known_open_exposure_status"], "KNOWN")
            finally:
                store.close()

    def test_entry_fee_required_and_no_terminal_resurrect(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                pid = _open_filled(store, strategy, "SIGDEC-FEE-1", "2026-09-03T12:10:00Z")
                store._conn.execute(
                    "UPDATE positions SET entry_fee_usd_dec = NULL WHERE position_id = ?",
                    (pid,),
                )
                store._conn.commit()
                with self.assertRaises(PaperPlaneError) as ctx:
                    store.apply_paper_exit_fill(
                        position_id=pid, exit_unit_price_usd="1.10", mode="PAPER"
                    )
                self.assertEqual(str(ctx.exception), "EXIT_FILL_REQUIRES_ENTRY_FEE")
                store.apply_paper_entry_fill(
                    position_id=pid,
                    entry_unit_price_usd="1.00",
                    entry_gross_notional_usd="100",
                    fee_bps=10,
                    mode="PAPER",
                )
                store.apply_paper_exit_fill(
                    position_id=pid, exit_unit_price_usd="1.10", mode="PAPER"
                )
                with self.assertRaises(PaperPlaneError) as resurrect:
                    store.apply_paper_entry_fill(
                        position_id=pid,
                        entry_unit_price_usd="1.00",
                        entry_gross_notional_usd="100",
                        fee_bps=10,
                        mode="PAPER",
                    )
                self.assertIn("ENTRY_FILL_STATE_INVALID", str(resurrect.exception))
                unpriced = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_signal("SIGDEC-FEE-2", decision_at="2026-09-03T12:11:00Z"),
                    known_activation_epochs=KNOWN_EPOCHS,
                    mode="PAPER",
                    as_of="2026-09-03T12:11:00Z",
                )
                ops = build_operations_projection(store)
                self.assertIn(ops["known_open_exposure_status"], {"UNKNOWN", "PARTIAL_KNOWN"})
                row = next(
                    r
                    for r in ops["position_rows"]
                    if r["position_id"] == unpriced["position_id"]
                )
                self.assertIsNone(row["entered_notional_usd"])
            finally:
                store.close()

    def test_loss_streak_unknown_when_latest_unknown(self) -> None:
        rows = [
            {"net_pnl_usd": "1.00", "pnl_status": "KNOWN"},
            {"net_pnl_usd": None, "pnl_status": "UNKNOWN"},
        ]
        streak = compute_loss_streak(rows)
        self.assertEqual(streak["current_loss_streak_status"], "UNKNOWN")
        self.assertIsNone(streak["current_loss_streak_count"])
        self.assertEqual(compute_max_drawdown_usd(rows), "0")

    def test_pause_close_all_stop_drain_idempotent(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            store = PaperPlaneStore(path)
            try:
                p1 = _open_filled(store, strategy, "SIGDEC-CMD-1", "2026-09-03T12:10:00Z")
                p2 = _open_filled(store, strategy, "SIGDEC-CMD-2", "2026-09-03T12:11:00Z")
                bot_id = store.bots()[0]["bot_instance_id"]
                apply_operator_command(
                    store,
                    {
                        "command_type": "PAUSE_NEW_ENTRIES",
                        "idempotency_key": "K-PAUSE",
                        "bot_instance_id": bot_id,
                    },
                )
                with self.assertRaises(PaperPlaneError) as ctx:
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal(
                            "SIGDEC-CMD-BLOCKED", decision_at="2026-09-03T12:12:00Z"
                        ),
                        known_activation_epochs=KNOWN_EPOCHS,
                        mode="PAPER",
                        as_of="2026-09-03T12:12:00Z",
                    )
                self.assertEqual(str(ctx.exception), "ENTRIES_PAUSED")
                close_one = apply_operator_command(
                    store,
                    {
                        "command_type": "REQUEST_CLOSE_POSITION",
                        "idempotency_key": "K-CLOSE1",
                        "position_id": p1,
                    },
                )
                self.assertEqual(close_one["state"], "EXIT_REQUIRED")
                ops = build_operations_projection(store, bot_instance_id=bot_id)
                stale = apply_operator_command(
                    store,
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "idempotency_key": "K-STALE",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": "deadbeef",
                    },
                )
                self.assertEqual(stale["status"], "STALE_OPERATOR_SNAPSHOT")
                self.assertEqual(stale["side_effects"], 0)
                ok = apply_operator_command(
                    store,
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "idempotency_key": "K-OK",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": ops["open_position_set_sha256"],
                    },
                )
                self.assertEqual(ok["status"], "APPLIED")
                dup = apply_operator_command(
                    store,
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "idempotency_key": "K-OK",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": ops["open_position_set_sha256"],
                    },
                )
                self.assertTrue(dup["idempotent"])
                stop = apply_operator_command(
                    store,
                    {
                        "command_type": "STOP_BOT",
                        "idempotency_key": "K-STOP",
                        "bot_instance_id": bot_id,
                    },
                )
                self.assertEqual(stop["bot_status"], "DRAINING")
                with self.assertRaises(PaperPlaneError) as drain_ctx:
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal(
                            "SIGDEC-CMD-DRAIN", decision_at="2026-09-03T12:13:00Z"
                        ),
                        known_activation_epochs=KNOWN_EPOCHS,
                        mode="PAPER",
                        as_of="2026-09-03T12:13:00Z",
                    )
                self.assertEqual(str(drain_ctx.exception), "BOT_STATUS_BLOCKS_ENTRY:DRAINING")
                self.assertEqual(store.get_bot(bot_id)["status"], "DRAINING")
                with self.assertRaises(PaperPlaneError):
                    apply_operator_command(
                        store,
                        {
                            "command_type": "RESUME_NEW_ENTRIES",
                            "idempotency_key": "K-RESUME",
                            "bot_instance_id": bot_id,
                        },
                    )
                for pid in (p1, p2):
                    pos = store.get_position(pid)
                    assert pos is not None
                    if pos["state"] != "RECONCILED":
                        if pos.get("entry_price_dec"):
                            store.apply_paper_exit_fill(
                                position_id=pid, exit_unit_price_usd="1.00", mode="PAPER"
                            )
                finished = maybe_finish_drain(store, bot_id)
                self.assertEqual(finished["bot_status"], "STOPPED")
                store.close()
                store = None  # type: ignore[assignment]
                store2 = PaperPlaneStore(path)
                try:
                    self.assertEqual(store2.get_bot(bot_id)["status"], "STOPPED")
                    self.assertIsNotNone(store2.get_operator_command("K-OK"))
                    self.assertGreaterEqual(len(store2.execution_events()), 1)
                finally:
                    store2.close()
            finally:
                if store is not None:
                    store.close()

    def test_pause_resume_happy_path(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _open_filled(store, strategy, "SIGDEC-RES-1", "2026-09-03T12:10:00Z")
                bot_id = store.bots()[0]["bot_instance_id"]
                apply_operator_command(
                    store,
                    {
                        "command_type": "PAUSE_NEW_ENTRIES",
                        "idempotency_key": "K-RES-PAUSE",
                        "bot_instance_id": bot_id,
                    },
                )
                with self.assertRaises(PaperPlaneError):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal(
                            "SIGDEC-RES-BLOCK", decision_at="2026-09-03T12:11:00Z"
                        ),
                        known_activation_epochs=KNOWN_EPOCHS,
                        mode="PAPER",
                        as_of="2026-09-03T12:11:00Z",
                    )
                apply_operator_command(
                    store,
                    {
                        "command_type": "RESUME_NEW_ENTRIES",
                        "idempotency_key": "K-RES-RESUME",
                        "bot_instance_id": bot_id,
                    },
                )
                pid = _open_filled(store, strategy, "SIGDEC-RES-2", "2026-09-03T12:12:00Z")
                self.assertEqual(store.get_position(pid)["state"], "OPEN")
            finally:
                store.close()

    def test_shadow_evidence_class_separate(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                accepted = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_signal("SIGDEC-SHADOW-1"),
                    known_activation_epochs={EPOCH: {"mode": "SHADOW"}},
                    mode="SHADOW",
                )
                pid = str(accepted["position_id"])
                store.apply_paper_entry_fill(
                    position_id=pid,
                    entry_unit_price_usd="1.00",
                    entry_gross_notional_usd="100",
                    fee_bps=10,
                    mode="SHADOW",
                )
                store.apply_paper_exit_fill(
                    position_id=pid, exit_unit_price_usd="1.10", mode="SHADOW"
                )
                pos = store.get_position(pid)
                assert pos is not None
                self.assertEqual(pos["pnl_evidence_class"], "SHADOW_RECONCILED_QUOTE_MODEL")
                self.assertEqual(pos["realized_net_pnl_usd_dec"], "9.79")
            finally:
                store.close()

    def test_smoke_script_pass(self) -> None:
        sys.path.insert(0, str(ROOT))
        from scripts.factory_paper_shadow_operator_smoke import run_smoke

        result = run_smoke()
        self.assertEqual(result["terminal"], "PAPER_SHADOW_ACCOUNTING_CONTROL_PASS")
        self.assertEqual(result["loss_streak_count"], 2)
        self.assertEqual(result["max_drawdown_usd"], "30.37")
        self.assertEqual(result["provider_calls"], 0)


if __name__ == "__main__":
    unittest.main()
