"""PAPER_SHADOW_EXECUTION_INTEGRITY series vertical acceptance.

One module for the series; every atom adds one TestCase class. Declared in
configs/execution_domain_v1.json -> required_fast_test_modules.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import solana_alpha_lab.factory.paper_plane as paper_plane  # noqa: E402
from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    accept_signal_decision,
)
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command  # noqa: E402
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402

STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}
MINT = "So11111111111111111111111111111111111111112"
MINT_B = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
T0 = "2026-09-03T12:10:00Z"
RACE_ITERATIONS = int(os.environ.get("PAPER_PLANE_RACE_ITERATIONS", "40"))


def signal(
    signal_id: str, *, decision_at: str = T0, mint: str = MINT, action: str = "ENTER"
) -> dict[str, Any]:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": "V1",
        "activation_epoch_id": EPOCH,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": mint,
        "decision_at": decision_at,
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": action,
        "reason_code": "VERTICAL_ENTER",
        "evidence_refs": ["sha256:" + "d" * 64],
    }


def accept(
    store: PaperPlaneStore,
    strategy: dict[str, Any],
    signal_id: str,
    *,
    as_of: str | None = T0,
    skip_fill: bool = False,
    **signal_fields: Any,
) -> dict[str, Any]:
    return accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=signal(signal_id, **signal_fields),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of=as_of,
        skip_fill=skip_fill,
    )


def open_filled(
    store: PaperPlaneStore, strategy: dict[str, Any], signal_id: str, *, price: str = "1.00"
) -> str:
    pid = str(accept(store, strategy, signal_id)["position_id"])
    store.apply_paper_entry_fill(
        position_id=pid,
        entry_unit_price_usd=price,
        entry_gross_notional_usd=str(strategy["notional_policy"]["notional_usd"]),
        fee_bps=int(strategy["notional_policy"]["fee_bps"]),
        mode="PAPER",
    )
    return pid


def event_types(
    store: PaperPlaneStore,
    *,
    position_id: str | None = None,
    signal_decision_id: str | None = None,
) -> list[str]:
    selected: list[str] = []
    for event in store.execution_events():
        payload = event.get("payload") or {}
        if position_id is not None and event.get("position_id") == position_id:
            selected.append(str(event["event_type"]))
        elif signal_decision_id is not None and payload.get("signal_decision_id") == signal_decision_id:
            selected.append(str(event["event_type"]))
    return selected


@contextmanager
def fail_once_on_event(target: str) -> Iterator[None]:
    """Crash the first append of `target` to emulate a process death after the state write."""

    original = PaperPlaneStore.append_execution_event
    fired = {"done": False}

    def failing(self: PaperPlaneStore, **kwargs: Any) -> str:
        if kwargs.get("event_type") == target and not fired["done"]:
            fired["done"] = True
            raise RuntimeError(f"INJECTED_CRASH:{target}")
        return original(self, **kwargs)

    PaperPlaneStore.append_execution_event = failing  # type: ignore[method-assign]
    try:
        yield
    finally:
        PaperPlaneStore.append_execution_event = original  # type: ignore[method-assign]


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = load_strategy_version(ROOT, STRAT_REL)
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dir = Path(self._tmp.name)
        self._stores: list[PaperPlaneStore] = []

    def tearDown(self) -> None:
        for opened in self._stores:
            opened.close()
        self._tmp.cleanup()

    def store(self, name: str = "paper.sqlite") -> PaperPlaneStore:
        opened = PaperPlaneStore(self.dir / name)
        self._stores.append(opened)
        return opened

    def close_request(self, store: PaperPlaneStore, pid: str, key: str) -> dict[str, Any]:
        return apply_operator_command(
            store,
            {"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": key, "position_id": pid},
        )


class WriteIntegrityTests(StoreCase):
    """A1 PAPER_PLANE_WRITE_INTEGRITY_V1."""

    def test_close_request_serializes_with_concurrent_exit_fill(self) -> None:
        operator_store = self.store("race.sqlite")
        runner_store = self.store("race.sqlite")
        pid = open_filled(operator_store, self.strategy, "SIGDEC-VERT-RACE-1")
        inside = threading.Event()
        outcome: dict[str, Any] = {}
        original = paper_plane.TRANSITIONS

        class HoldInsideTransition(dict):
            def get(self, key: Any, default: Any = None) -> Any:
                if (
                    key == "OPEN"
                    and threading.current_thread().name == "operator"
                    and not inside.is_set()
                ):
                    inside.set()
                    time.sleep(0.3)
                return dict.get(self, key, default)

        def operator() -> None:
            try:
                outcome["operator"] = self.close_request(operator_store, pid, "IDEM-VERT-RACE-1")
            except PaperPlaneError as exc:
                outcome["operator_error"] = str(exc)

        def runner() -> None:
            inside.wait(5)
            try:
                runner_store.apply_paper_exit_fill(
                    position_id=pid, exit_unit_price_usd="1.10", mode="PAPER"
                )
            except Exception as exc:  # noqa: BLE001 - asserted below
                outcome["runner_error"] = f"{type(exc).__name__}:{exc}"

        paper_plane.TRANSITIONS = HoldInsideTransition(original)
        try:
            threads = [
                threading.Thread(target=operator, name="operator"),
                threading.Thread(target=runner, name="runner"),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(20)
        finally:
            paper_plane.TRANSITIONS = original
        self.assertNotIn("runner_error", outcome)
        self.assertEqual(operator_store.get_position(pid)["state"], "RECONCILED")
        types = event_types(operator_store, position_id=pid)
        self.assertEqual(types.count("PAPER_EXIT_OBSERVED"), 1)
        self.assertEqual(types.count("RECONCILIATION"), 1)

    def test_close_vs_exit_race_never_regresses_or_duplicates(self) -> None:
        failures: list[str] = []
        for index in range(RACE_ITERATIONS):
            path = self.dir / f"stochastic-{index}.sqlite"
            first = PaperPlaneStore(path)
            second = PaperPlaneStore(path)
            try:
                pid = open_filled(first, self.strategy, f"SIGDEC-VERT-STO-{index}")
                barrier = threading.Barrier(2)

                def operator(store: PaperPlaneStore = first, key: str = f"IDEM-VERT-STO-{index}") -> None:
                    barrier.wait()
                    try:
                        self.close_request(store, pid, key)
                    except PaperPlaneError:
                        pass

                def runner(store: PaperPlaneStore = second) -> None:
                    barrier.wait()
                    try:
                        store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd="1.10", mode="PAPER")
                    except PaperPlaneError:
                        pass

                threads = [threading.Thread(target=operator), threading.Thread(target=runner)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(20)
                row = first.get_position(pid)
                reconciliations = event_types(first, position_id=pid).count("RECONCILIATION")
                if row["state"] != "RECONCILED" or reconciliations != 1:
                    failures.append(f"{index}:{row['state']}:{reconciliations}")
            finally:
                first.close()
                second.close()
        self.assertEqual(failures, [])

    def test_exit_fill_is_atomic_with_its_events(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-CRASH-EXIT")
        with fail_once_on_event("PAPER_EXIT_OBSERVED"):
            with self.assertRaises(RuntimeError):
                store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd="1.10", mode="PAPER")
        row = store.get_position(pid)
        self.assertEqual(row["state"], "OPEN")
        self.assertIsNone(row["realized_net_pnl_usd_dec"])
        self.assertNotIn("RECONCILIATION", event_types(store, position_id=pid))
        store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd="1.10", mode="PAPER")
        types = event_types(store, position_id=pid)
        self.assertEqual(store.get_position(pid)["state"], "RECONCILED")
        self.assertEqual(types.count("PAPER_EXIT_OBSERVED"), 1)
        self.assertEqual(types.count("RECONCILIATION"), 1)

    def test_unresolved_exit_is_atomic_with_its_reconciliation_event(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-CRASH-UNRES")
        with fail_once_on_event("RECONCILIATION"):
            with self.assertRaises(RuntimeError):
                store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=None, mode="PAPER")
        self.assertEqual(store.get_position(pid)["state"], "OPEN")
        store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=None, mode="PAPER")
        self.assertEqual(store.get_position(pid)["state"], "UNRESOLVED")
        self.assertEqual(event_types(store, position_id=pid).count("RECONCILIATION"), 1)

    def test_entry_fill_is_atomic_with_its_event(self) -> None:
        store = self.store()
        pid = str(accept(store, self.strategy, "SIGDEC-VERT-CRASH-ENTRY")["position_id"])
        fill = {
            "position_id": pid,
            "entry_unit_price_usd": "1.00",
            "entry_gross_notional_usd": str(self.strategy["notional_policy"]["notional_usd"]),
            "fee_bps": int(self.strategy["notional_policy"]["fee_bps"]),
            "mode": "PAPER",
        }
        with fail_once_on_event("PAPER_SIMULATION_OBSERVED"):
            with self.assertRaises(RuntimeError):
                store.apply_paper_entry_fill(**fill)
        self.assertIsNone(store.get_position(pid)["entry_price_dec"])
        store.apply_paper_entry_fill(**fill)
        self.assertEqual(event_types(store, position_id=pid).count("PAPER_SIMULATION_OBSERVED"), 1)

    def test_accept_fill_is_atomic_with_intent_events(self) -> None:
        store = self.store()
        pid = "POS-SIG-SIGDEC-VERT-CRASH-INTENT"
        with fail_once_on_event("EXECUTION_INTENT_CREATED"):
            with self.assertRaises(RuntimeError):
                accept(store, self.strategy, "SIGDEC-VERT-CRASH-INTENT")
        self.assertEqual(store.get_position(pid)["state"], "WATCHED")
        self.assertEqual(accept(store, self.strategy, "SIGDEC-VERT-CRASH-INTENT")["state"], "OPEN")
        types = event_types(store, position_id=pid)
        self.assertEqual(types.count("EXECUTION_INTENT_CREATED"), 1)
        self.assertEqual(types.count("POSITION_TRANSITION"), 1)

    def test_operator_command_is_atomic_with_its_record(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-CRASH-CMD")
        with fail_once_on_event("OPERATOR_COMMAND_APPLIED"):
            with self.assertRaises(RuntimeError):
                self.close_request(store, pid, "IDEM-VERT-CMD-1")
        self.assertEqual(store.get_position(pid)["state"], "OPEN")
        self.assertIsNone(store.get_operator_command("IDEM-VERT-CMD-1"))
        first = self.close_request(store, pid, "IDEM-VERT-CMD-1")
        again = self.close_request(store, pid, "IDEM-VERT-CMD-1")
        self.assertFalse(first["idempotent"])
        self.assertTrue(again["idempotent"])
        self.assertEqual(store.get_position(pid)["state"], "EXIT_REQUIRED")

    def test_concurrent_same_signal_accept_writes_intent_events_once(self) -> None:
        first = self.store("same.sqlite")
        second = self.store("same.sqlite")
        barrier = threading.Barrier(2)
        errors: list[str] = []

        def worker(store: PaperPlaneStore) -> None:
            barrier.wait()
            try:
                accept(store, self.strategy, "SIGDEC-VERT-SAME-1")
            except PaperPlaneError as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(s,)) for s in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        self.assertEqual(errors, [])
        pid = "POS-SIG-SIGDEC-VERT-SAME-1"
        self.assertEqual(first.get_position(pid)["state"], "OPEN")
        types = event_types(first, position_id=pid)
        self.assertEqual(types.count("EXECUTION_INTENT_CREATED"), 1)
        self.assertEqual(types.count("POSITION_TRANSITION"), 1)

    def test_execution_events_are_returned_in_causal_order(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-ORDER")
        store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd="1.10", mode="PAPER")
        self.assertEqual(
            event_types(store, signal_decision_id="SIGDEC-VERT-ORDER"),
            [
                "PRE_TRADE_RISK_SNAPSHOT",
                "SIGNAL_DECISION_ACCEPTED",
                "EXECUTION_INTENT_CREATED",
                "POSITION_TRANSITION",
                "PAPER_SIMULATION_OBSERVED",
                "PAPER_EXIT_OBSERVED",
                "RECONCILIATION",
            ],
        )


if __name__ == "__main__":
    unittest.main()
