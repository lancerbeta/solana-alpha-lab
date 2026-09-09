"""TradingRuntimePolicyV1 admission, sizing, revision and mode isolation."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
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
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import (  # noqa: E402
    GENESIS_POLICY_SHA256,
    STATUS_NOT_CONFIGURED,
    apply_policy,
    check_policy,
    effective_entry_notional,
    load_capability_config,
    rollback_policy,
    show_policy,
)

STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN = {EPOCH: {"mode": "PAPER"}, "ACTIVATION-EPOCH-ACCOUNTING-SHADOW-001": {"mode": "SHADOW"}}
MINT = "So11111111111111111111111111111111111111112"
MINT_B = "So22222222222222222222222222222222222222222"
PHRASE = "AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY"


def _signal(
    signal_id: str,
    *,
    decision_at: str = "2026-09-03T12:10:00Z",
    mint: str = MINT,
    strategy_id: str = "STRAT-ACCOUNTING-CONTROL-A",
    strategy_version: str = "V1",
    epoch: str = EPOCH,
) -> dict:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "activation_epoch_id": epoch,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": mint,
        "decision_at": decision_at,
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": "ENTER",
        "reason_code": "ACCOUNTING_FIXTURE_ENTER",
        "evidence_refs": [
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        ],
    }


def _enter(store: PaperPlaneStore, strategy: dict, signal_id: str, **kwargs) -> dict:
    return accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal(signal_id, **kwargs),
        known_activation_epochs=KNOWN,
        mode=kwargs.pop("mode", "PAPER") if False else kwargs.get("mode", "PAPER"),
        as_of=kwargs.get("decision_at", "2026-09-03T12:10:00Z"),
        skip_fill=kwargs.get("skip_fill", False),
    )


def _enter2(
    store: PaperPlaneStore,
    strategy: dict,
    signal_id: str,
    *,
    mode: str = "PAPER",
    mint: str = MINT,
    decision_at: str = "2026-09-03T12:10:00Z",
    skip_fill: bool = False,
    epoch: str | None = None,
) -> dict:
    epoch_id = epoch or (
        EPOCH if mode == "PAPER" else "ACTIVATION-EPOCH-ACCOUNTING-SHADOW-001"
    )
    return accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal(
            signal_id,
            decision_at=decision_at,
            mint=mint,
            epoch=epoch_id,
        ),
        known_activation_epochs=KNOWN,
        mode=mode,
        as_of=decision_at,
        skip_fill=skip_fill,
    )


def _candidate(**overrides) -> dict:
    body = {
        "new_entries_enabled": True,
        "global_entry_notional_cap_usd": "10",
        "max_total_open_positions": 10,
        "max_total_open_notional_usd": "100",
        "default_strategy_max_open_positions": 3,
        "default_strategy_max_open_notional_usd": "30",
        "max_open_positions_per_mint": 2,
        "max_open_notional_per_mint_usd": "20",
        "strategy_overrides": {},
    }
    body.update(overrides)
    return body


def _apply(store: PaperPlaneStore, mode: str, candidate: dict, *, key: str, reason: str = "TEST") -> dict:
    shown = show_policy(store, mode)
    return apply_policy(
        ROOT,
        store,
        mode=mode,
        candidate_raw=candidate,
        expected_current_sha256=str(shown["policy_sha256"]),
        idempotency_key=key,
        owner_authorization_phrase=PHRASE,
        reason=reason,
    )


class TradingRuntimePolicyTests(unittest.TestCase):
    def test_absent_policy_preserves_strategy_only_paper_and_shadow(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                paper = show_policy(store, "PAPER")
                shadow = show_policy(store, "SHADOW")
                self.assertEqual(paper["status"], STATUS_NOT_CONFIGURED)
                self.assertEqual(shadow["status"], STATUS_NOT_CONFIGURED)
                opened = _enter2(store, strategy, "SIGDEC-ABSENT-1")
                self.assertTrue(opened["opened"])
                self.assertEqual(
                    opened["admitted_entry_notional_usd_dec"],
                    "100",
                )
                shadow_open = _enter2(
                    store,
                    strategy,
                    "SIGDEC-ABSENT-S1",
                    mode="SHADOW",
                    decision_at="2026-09-03T12:11:00Z",
                )
                self.assertTrue(shadow_open["opened"])
            finally:
                store.close()

    def test_sizing_min_and_no_headroom_shrink(self) -> None:
        self.assertEqual(
            effective_entry_notional(
                strategy_requested=Decimal("100"), runtime_cap=Decimal("10")
            ),
            Decimal("10"),
        )
        self.assertEqual(
            effective_entry_notional(
                strategy_requested=Decimal("5"), runtime_cap=Decimal("10")
            ),
            Decimal("5"),
        )
        self.assertEqual(
            effective_entry_notional(
                strategy_requested=Decimal("100"), runtime_cap=Decimal("500")
            ),
            Decimal("100"),
        )
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _apply(
                    store,
                    "PAPER",
                    _candidate(
                        global_entry_notional_cap_usd="10",
                        max_total_open_notional_usd="16",
                        max_total_open_positions=10,
                    ),
                    key="IDEM-SIZE-1",
                )
                first = _enter2(store, strategy, "SIGDEC-SIZE-1")
                self.assertEqual(first["admitted_entry_notional_usd_dec"], "10")
                with self.assertRaises(PaperPlaneError) as exc:
                    _enter2(
                        store,
                        strategy,
                        "SIGDEC-SIZE-2",
                        decision_at="2026-09-03T12:11:00Z",
                    )
                self.assertIn("BLOCK_GLOBAL_OPEN_NOTIONAL", str(exc.exception))
            finally:
                store.close()

    def test_position_and_notional_caps(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _apply(
                    store,
                    "PAPER",
                    _candidate(
                        global_entry_notional_cap_usd="10",
                        max_total_open_positions=1,
                        default_strategy_max_open_positions=1,
                        max_open_positions_per_mint=1,
                    ),
                    key="IDEM-POS-1",
                )
                _enter2(store, strategy, "SIGDEC-POS-1")
                with self.assertRaises(PaperPlaneError) as exc:
                    _enter2(
                        store,
                        strategy,
                        "SIGDEC-POS-2",
                        mint=MINT_B,
                        decision_at="2026-09-03T12:11:00Z",
                    )
                self.assertTrue(
                    any(
                        token in str(exc.exception)
                        for token in (
                            "BLOCK_GLOBAL_MAX_OPEN_POSITIONS",
                            "BLOCK_MAX_OPEN_POSITIONS",
                        )
                    )
                )
            finally:
                store.close()

    def test_unknown_open_risk_blocks_historical_does_not(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _apply(
                    store,
                    "PAPER",
                    _candidate(max_total_open_notional_usd="100"),
                    key="IDEM-UNK-1",
                )
                opened = _enter2(store, strategy, "SIGDEC-UNK-1")
                store._conn.execute(
                    """
                    UPDATE positions
                    SET admitted_entry_notional_usd_dec = NULL,
                        entered_notional_usd_dec = NULL,
                        entered_notional_usd = NULL
                    WHERE position_id = ?
                    """,
                    (opened["position_id"],),
                )
                with self.assertRaises(PaperPlaneError) as exc:
                    _enter2(
                        store,
                        strategy,
                        "SIGDEC-UNK-2",
                        mint=MINT_B,
                        decision_at="2026-09-03T12:11:00Z",
                    )
                self.assertIn("RUNTIME_EXPOSURE_UNKNOWN", str(exc.exception))
                store.transition(opened["position_id"], "EXIT_REQUIRED")
                store.transition(opened["position_id"], "EXITING")
                store.transition(opened["position_id"], "CLOSED")
                store.transition(opened["position_id"], "RECONCILED")
                again = _enter2(
                    store,
                    strategy,
                    "SIGDEC-UNK-3",
                    mint=MINT_B,
                    decision_at="2026-09-03T12:12:00Z",
                )
                self.assertTrue(again["opened"])
            finally:
                store.close()

    def test_entry_stop_and_revision_semantics(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                first = _apply(store, "PAPER", _candidate(), key="IDEM-STOP-1")
                opened = _enter2(store, strategy, "SIGDEC-STOP-1")
                frozen = store.get_position(opened["position_id"])
                assert frozen is not None
                self.assertEqual(frozen["runtime_policy_revision"], 1)
                stopped = _apply(
                    store,
                    "PAPER",
                    _candidate(new_entries_enabled=False, global_entry_notional_cap_usd="1"),
                    key="IDEM-STOP-2",
                )
                self.assertEqual(stopped["revision"], 2)
                with self.assertRaises(PaperPlaneError) as exc:
                    _enter2(
                        store,
                        strategy,
                        "SIGDEC-STOP-2",
                        decision_at="2026-09-03T12:11:00Z",
                    )
                self.assertIn("BLOCK_NEW_ENTRIES_DISABLED", str(exc.exception))
                refreshed = store.get_position(opened["position_id"])
                assert refreshed is not None
                self.assertEqual(refreshed["admitted_entry_notional_usd_dec"], "10")
                self.assertEqual(refreshed["runtime_policy_revision"], 1)
                store.transition(opened["position_id"], "EXIT_REQUIRED")
                self.assertEqual(store.get_position(opened["position_id"])["state"], "EXIT_REQUIRED")
                stale = show_policy(store, "PAPER")
                with self.assertRaises(Exception) as stale_exc:
                    apply_policy(
                        ROOT,
                        store,
                        mode="PAPER",
                        candidate_raw=_candidate(),
                        expected_current_sha256=str(first["policy_sha256"]),
                        idempotency_key="IDEM-STALE",
                        owner_authorization_phrase=PHRASE,
                        reason="STALE",
                    )
                self.assertIn("POLICY_STALE_WRITE_DENIED", str(stale_exc.exception))
                again = apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw=_candidate(new_entries_enabled=False),
                    expected_current_sha256=str(stale["policy_sha256"]),
                    idempotency_key="IDEM-STOP-2",
                    owner_authorization_phrase=PHRASE,
                    reason="DUP",
                )
                self.assertTrue(again["idempotent"])
                rolled = rollback_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    expected_current_sha256=str(show_policy(store, "PAPER")["policy_sha256"]),
                    idempotency_key="IDEM-ROLL-1",
                    owner_authorization_phrase=PHRASE,
                )
                self.assertEqual(rolled["readback"]["revision"], 3)
                self.assertEqual(len(show_policy(store, "PAPER")["history"]), 3)
            finally:
                store.close()

    def test_paper_shadow_isolation_and_live_denied(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _apply(
                    store,
                    "PAPER",
                    _candidate(max_total_open_positions=1),
                    key="IDEM-MODE-P",
                )
                _enter2(store, strategy, "SIGDEC-MODE-P")
                shadow = _enter2(
                    store,
                    strategy,
                    "SIGDEC-MODE-S",
                    mode="SHADOW",
                    decision_at="2026-09-03T12:11:00Z",
                )
                self.assertTrue(shadow["opened"])
                with self.assertRaises(Exception) as exc:
                    show_policy(store, "LIVE")
                self.assertIn("LIVE_NOT_SUPPORTED", str(exc.exception))
            finally:
                store.close()

    def test_readonly_get_does_not_create_or_apply(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            writer = PaperPlaneStore(path)
            writer.close()
            before = path.stat().st_mtime_ns
            reader = PaperPlaneStore(path, readonly=True)
            try:
                shown = show_policy(reader, "PAPER")
                self.assertEqual(shown["status"], STATUS_NOT_CONFIGURED)
            finally:
                reader.close()
            self.assertEqual(path.stat().st_mtime_ns, before)
            conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
            try:
                count = conn.execute(
                    "SELECT COUNT(*) FROM trading_runtime_policy_revisions"
                ).fetchone()[0]
                self.assertEqual(count, 0)
            finally:
                conn.close()

    def test_capability_phrase_is_not_a_runtime_value(self) -> None:
        config = load_capability_config(ROOT)
        self.assertEqual(config["owner_authorization_phrase"], PHRASE)
        self.assertNotIn("10", json.dumps(config))
        self.assertIs(config.get("live_supported"), False)

    def test_check_classifies_tightening(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                checked = check_policy(store, mode="PAPER", candidate_raw=_candidate())
                self.assertEqual(checked["classification"], "TIGHTENING")
                self.assertEqual(checked["expected_current_sha256"], GENESIS_POLICY_SHA256)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
