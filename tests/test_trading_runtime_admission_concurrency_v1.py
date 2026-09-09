"""Concurrent ENTER and crash/retry proofs for TradingRuntimePolicyV1."""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    OPEN_RISK_STATES,
    PaperPlaneStore,
    accept_signal_decision,
)
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, show_policy  # noqa: E402
from tests.test_trading_runtime_policy_v1 import (  # noqa: E402
    EPOCH,
    KNOWN,
    MINT,
    PHRASE,
    STRAT_REL,
    _candidate,
    _enter2,
    _signal,
)

MINT_B = "So22222222222222222222222222222222222222222"


class TradingRuntimeAdmissionConcurrencyTests(unittest.TestCase):
    def test_two_distinct_enters_one_remaining_slot(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            bootstrap = PaperPlaneStore(path)
            apply_policy(
                ROOT,
                bootstrap,
                mode="PAPER",
                candidate_raw=_candidate(max_total_open_positions=1),
                expected_current_sha256=str(show_policy(bootstrap, "PAPER")["policy_sha256"]),
                idempotency_key="IDEM-CONC-BOOT",
                owner_authorization_phrase=PHRASE,
                reason="CONC",
            )
            bootstrap.close()
            results: list[str] = []
            lock = threading.Lock()

            def _worker(signal_id: str, mint: str) -> None:
                store = PaperPlaneStore(path)
                try:
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal(signal_id, mint=mint),
                        known_activation_epochs=KNOWN,
                        mode="PAPER",
                        as_of="2026-09-03T12:10:00Z",
                    )
                    with lock:
                        results.append("ALLOW")
                except Exception as exc:
                    with lock:
                        results.append(str(exc))
                finally:
                    store.close()

            threads = [
                threading.Thread(target=_worker, args=("SIGDEC-CONC-A", MINT)),
                threading.Thread(target=_worker, args=("SIGDEC-CONC-B", MINT_B)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            allows = [item for item in results if item == "ALLOW"]
            blocks = [item for item in results if item != "ALLOW"]
            self.assertEqual(len(allows), 1, results)
            self.assertEqual(len(blocks), 1, results)
            self.assertTrue(any("BLOCK" in item for item in blocks), results)
            verify = PaperPlaneStore(path)
            try:
                open_risk = [
                    row
                    for row in verify.positions()
                    if str(row["state"]) in OPEN_RISK_STATES
                ]
                self.assertEqual(len(open_risk), 1)
            finally:
                verify.close()

    def test_shared_store_two_threads_one_remaining_slot(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw=_candidate(max_total_open_positions=1),
                    expected_current_sha256=str(show_policy(store, "PAPER")["policy_sha256"]),
                    idempotency_key="IDEM-SHARED-BOOT",
                    owner_authorization_phrase=PHRASE,
                    reason="CONC",
                )
                results: list[str] = []
                lock = threading.Lock()

                def _worker(signal_id: str, mint: str) -> None:
                    try:
                        accept_signal_decision(
                            ROOT,
                            store,
                            strategy=strategy,
                            signal_decision=_signal(signal_id, mint=mint),
                            known_activation_epochs=KNOWN,
                            mode="PAPER",
                            as_of="2026-09-03T12:10:00Z",
                        )
                        with lock:
                            results.append("ALLOW")
                    except Exception as exc:
                        with lock:
                            results.append(str(exc))

                threads = [
                    threading.Thread(target=_worker, args=("SIGDEC-SHARED-A", MINT)),
                    threading.Thread(target=_worker, args=("SIGDEC-SHARED-B", MINT_B)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                allows = [item for item in results if item == "ALLOW"]
                blocks = [item for item in results if item != "ALLOW"]
                self.assertEqual(len(allows), 1, results)
                self.assertEqual(len(blocks), 1, results)
                self.assertTrue(any("BLOCK" in item for item in blocks), results)
                open_risk = [
                    row
                    for row in store.positions()
                    if str(row["state"]) in OPEN_RISK_STATES
                ]
                self.assertEqual(len(open_risk), 1)
            finally:
                store.close()

    def test_same_signal_retry_one_position(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            PaperPlaneStore(path).close()
            ids: list[str] = []
            errors: list[str] = []

            lock = threading.Lock()

            def _worker() -> None:
                store = PaperPlaneStore(path)
                try:
                    result = accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal("SIGDEC-RETRY-1"),
                        known_activation_epochs=KNOWN,
                        mode="PAPER",
                        as_of="2026-09-03T12:10:00Z",
                    )
                    with lock:
                        ids.append(str(result["position_id"]))
                except Exception as exc:
                    with lock:
                        errors.append(str(exc))
                finally:
                    store.close()

            threads = [threading.Thread(target=_worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertFalse(errors, errors)
            self.assertEqual(len(set(ids)), 1, ids)
            store = PaperPlaneStore(path)
            try:
                self.assertEqual(len(store.positions()), 1)
            finally:
                store.close()

    def test_crash_after_allow_retry_keeps_binding(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw=_candidate(global_entry_notional_cap_usd="10"),
                    expected_current_sha256=str(show_policy(store, "PAPER")["policy_sha256"]),
                    idempotency_key="IDEM-CRASH-1",
                    owner_authorization_phrase=PHRASE,
                    reason="CRASH",
                )
                reserved = _enter2(
                    store, strategy, "SIGDEC-CRASH-1", skip_fill=True
                )
                position = store.get_position(reserved["position_id"])
                assert position is not None
                self.assertNotEqual(position["state"], "OPEN")
                self.assertEqual(position["admitted_entry_notional_usd_dec"], "10")
                self.assertEqual(position["runtime_policy_revision"], 1)
                self.assertIn(position["state"], OPEN_RISK_STATES)
                apply_policy(
                    ROOT,
                    store,
                    mode="PAPER",
                    candidate_raw=_candidate(global_entry_notional_cap_usd="1"),
                    expected_current_sha256=str(show_policy(store, "PAPER")["policy_sha256"]),
                    idempotency_key="IDEM-CRASH-2",
                    owner_authorization_phrase=PHRASE,
                    reason="LATER",
                )
                retried = _enter2(store, strategy, "SIGDEC-CRASH-1")
                self.assertEqual(retried["position_id"], reserved["position_id"])
                again = store.get_position(retried["position_id"])
                assert again is not None
                self.assertEqual(again["admitted_entry_notional_usd_dec"], "10")
                self.assertEqual(again["runtime_policy_revision"], 1)
                self.assertEqual(again["state"], "OPEN")
                self.assertEqual(len(store.positions()), 1)
            finally:
                store.close()

    def test_policy_apply_and_enter_do_not_mix_revisions(self) -> None:
        strategy = load_strategy_version(ROOT, STRAT_REL)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            bootstrap = PaperPlaneStore(path)
            apply_policy(
                ROOT,
                bootstrap,
                mode="PAPER",
                candidate_raw=_candidate(global_entry_notional_cap_usd="10"),
                expected_current_sha256=str(show_policy(bootstrap, "PAPER")["policy_sha256"]),
                idempotency_key="IDEM-RACE-0",
                owner_authorization_phrase=PHRASE,
                reason="BASE",
            )
            expected = str(show_policy(bootstrap, "PAPER")["policy_sha256"])
            bootstrap.close()
            errors: list[str] = []

            def _apply() -> None:
                store = PaperPlaneStore(path)
                try:
                    apply_policy(
                        ROOT,
                        store,
                        mode="PAPER",
                        candidate_raw=_candidate(global_entry_notional_cap_usd="7"),
                        expected_current_sha256=expected,
                        idempotency_key="IDEM-RACE-APPLY",
                        owner_authorization_phrase=PHRASE,
                        reason="RACE",
                    )
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    store.close()

            def _enter() -> None:
                store = PaperPlaneStore(path)
                try:
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_signal("SIGDEC-RACE-1"),
                        known_activation_epochs=KNOWN,
                        mode="PAPER",
                        as_of="2026-09-03T12:10:00Z",
                    )
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    store.close()

            threads = [
                threading.Thread(target=_apply),
                threading.Thread(target=_enter),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            store = PaperPlaneStore(path)
            try:
                positions = store.positions()
                if positions:
                    bound = positions[0]
                    sha = bound.get("runtime_policy_sha256")
                    rev = bound.get("runtime_policy_revision")
                    row = store.runtime_policy_by_sha256("PAPER", str(sha))
                    self.assertIsNotNone(row)
                    assert row is not None
                    self.assertEqual(int(row["revision"]), int(rev))
                    admitted = bound.get("admitted_entry_notional_usd_dec")
                    self.assertIn(admitted, {"10", "7"})
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
