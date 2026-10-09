"""PAPER_SHADOW_EXECUTION_INTEGRITY series vertical acceptance.

One module for the series; every atom adds one TestCase class. Declared in
configs/execution_domain_v1.json -> required_fast_test_modules.
"""

from __future__ import annotations

import os
import hashlib
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
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
    accept_exit_decision,
    accept_signal_decision,
)
from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.strategy_runtime import validate_and_hash_strategy  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import check_policy  # noqa: E402
import yaml  # noqa: E402
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection  # noqa: E402
from solana_alpha_lab.factory.paper_shadow_commands import (  # noqa: E402
    apply_operator_command,
    maybe_finish_drain,
)
from solana_alpha_lab.factory.strategy_runtime import (  # noqa: E402
    canonical_spec_sha256,
    load_strategy_version,
)
from solana_alpha_lab.factory.paper_shadow_operations import (  # noqa: E402
    build_operations_projection,
)
from solana_alpha_lab.factory.trading_operations import compose_trading_operations  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, show_policy  # noqa: E402

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

    def test_accounting_fixture_projection_scalars_survive_event_reorder(self) -> None:
        """DoD §5.5: accounting-fixture economics and trace scalars ignore event order.

        A second pass stamps one created_at and a conflicting later reason_code so
        first-wins is actually order-sensitive, then checks causal order keeps the
        earliest reason.
        """

        store = self.store()
        journey = (
            ("SIGDEC-T-P1", "2026-09-03T12:10:00Z", "1.10"),
            ("SIGDEC-T-P2", "2026-09-03T12:11:00Z", "0.90"),
            ("SIGDEC-T-P3", "2026-09-03T12:12:00Z", "0.80"),
        )
        for signal_id, decision_at, exit_price in journey:
            decision = signal(signal_id, decision_at=decision_at)
            decision["reason_code"] = "ACCOUNTING_FIXTURE_ENTER"
            decision["evidence_refs"] = [
                "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ]
            accepted = accept_signal_decision(
                ROOT,
                store,
                strategy=self.strategy,
                signal_decision=decision,
                known_activation_epochs=KNOWN_EPOCHS,
                mode="PAPER",
                as_of=decision_at,
            )
            pid = str(accepted["position_id"])
            store.apply_paper_entry_fill(
                position_id=pid,
                entry_unit_price_usd="1.00",
                entry_gross_notional_usd=str(self.strategy["notional_policy"]["notional_usd"]),
                fee_bps=int(self.strategy["notional_policy"]["fee_bps"]),
                mode="PAPER",
            )
            store.apply_paper_exit_fill(
                position_id=pid, exit_unit_price_usd=exit_price, mode="PAPER"
            )
        ops = build_operations_projection(store)
        by_state = {row["state"]: row for row in ops["position_rows"]}
        self.assertEqual(ops["current_loss_streak_count"], 2)
        self.assertEqual(ops["max_drawdown_usd"], "30.37")
        self.assertEqual(by_state["RECONCILED"]["pnl_evidence_class"], "PAPER_RECONCILED_MODEL")
        nets = sorted(row["net_pnl_usd"] for row in ops["position_rows"])
        self.assertEqual(set(nets), {"-20.18", "-10.19", "9.79"})

        fields = (
            "signal_decision_id",
            "position_id",
            "strategy_id",
            "activation_epoch_id",
            "mint",
            "decision_at",
            "action",
            "reason_code",
            "blocker",
            "stop_stage",
            "stages",
        )

        def slim(document: dict[str, Any]) -> list[dict[str, Any]]:
            rows = [
                {field: row.get(field) for field in fields}
                for row in document["traces"]
                if str(row.get("signal_decision_id") or "").startswith("SIGDEC-T-P")
            ]
            return sorted(rows, key=lambda row: str(row["signal_decision_id"]))

        causal = compose_trading_operations(ROOT, store)
        reversed_events = list(reversed(store.execution_events()))
        store.execution_events = lambda: reversed_events  # type: ignore[method-assign]
        reversed_view = compose_trading_operations(ROOT, store)
        self.assertEqual(slim(causal), slim(reversed_view))
        self.assertNotEqual(
            [event["event_type"] for event in store.execution_events()],
            [event["event_type"] for event in reversed(reversed_events)],
        )

        stamped = []
        for index, event in enumerate(store.execution_events()):
            item = dict(event)
            payload = dict(item.get("payload") or {})
            item["created_at"] = "2026-09-03T12:10:00Z"
            if index == len(reversed_events) - 1:
                payload["reason_code"] = "CONFLICT_REASON"
            item["payload"] = payload
            stamped.append(item)
        store.execution_events = lambda: stamped  # type: ignore[method-assign]
        conflicted = compose_trading_operations(ROOT, store)
        reasons = {
            row["signal_decision_id"]: row["reason_code"]
            for row in conflicted["traces"]
            if str(row.get("signal_decision_id") or "").startswith("SIGDEC-T-P")
        }
        self.assertTrue(set(reasons.values()) <= {"ACCOUNTING_FIXTURE_ENTER", "CONFLICT_REASON"})
        self.assertIn("ACCOUNTING_FIXTURE_ENTER", reasons.values())
        store.execution_events = lambda: list(reversed(stamped))  # type: ignore[method-assign]
        flipped = compose_trading_operations(ROOT, store)
        flipped_reasons = {
            row["signal_decision_id"]: row["reason_code"]
            for row in flipped["traces"]
            if row.get("signal_decision_id") in reasons
        }
        self.assertTrue(
            any(
                reasons[key] != flipped_reasons[key]
                for key in reasons
                if key in flipped_reasons
            )
        )


POLICY_PHRASE = "AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY"


def apply_paper_policy(store: PaperPlaneStore, key: str, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"new_entries_enabled": True, "strategy_overrides": {}}
    body.update(fields)
    return apply_policy(
        ROOT,
        store,
        mode="PAPER",
        candidate_raw=body,
        expected_current_sha256=str(show_policy(store, "PAPER")["policy_sha256"]),
        idempotency_key=key,
        owner_authorization_phrase=POLICY_PHRASE,
        reason="VERTICAL",
    )


def walk_to(store: PaperPlaneStore, pid: str, *states: str) -> None:
    for state in states:
        store.transition(pid, state)


class _NoResearch:
    def iter_committed_records(self) -> list[Any]:
        return []


class EntryIntentIntegrityTests(StoreCase):
    """A2 PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1."""

    def reserve(self, store: PaperPlaneStore, sid: str) -> dict[str, Any]:
        reserved = accept(store, self.strategy, sid, skip_fill=True)
        self.assertEqual(store.get_position(reserved["position_id"])["state"], "WATCHED")
        return reserved

    def test_stops_cancel_reserved_intents_instead_of_opening_them(self) -> None:
        cases = {
            "PAUSE": ("ENTRIES_PAUSED", "ENTRIES_PAUSED"),
            "DISABLED": ("BLOCK_NEW_ENTRIES_DISABLED", "NEW_ENTRIES_DISABLED"),
            "INVALID": ("RUNTIME_POLICY_INVALID", "RUNTIME_POLICY_INVALID"),
            "DRAINING": ("BOT_STATUS_BLOCKS_ENTRY:DRAINING", "BOT_DRAINING"),
        }
        for variant, (code, reason) in cases.items():
            with self.subTest(variant=variant):
                store = self.store(f"stop-{variant}.sqlite")
                sid = f"SIGDEC-VERT-STOP-{variant}"
                reserved = self.reserve(store, sid)
                bot = reserved["bot_instance_id"]
                if variant == "PAUSE":
                    apply_operator_command(
                        store,
                        {
                            "command_type": "PAUSE_NEW_ENTRIES",
                            "idempotency_key": f"IDEM-{variant}",
                            "bot_instance_id": bot,
                        },
                    )
                elif variant == "DISABLED":
                    apply_paper_policy(store, f"IDEM-{variant}", new_entries_enabled=False)
                elif variant == "INVALID":
                    apply_paper_policy(store, f"IDEM-{variant}")
                    store._conn.execute(
                        "UPDATE trading_runtime_policy_revisions SET policy_json = '{' WHERE mode = 'PAPER'"
                    )
                else:
                    store.set_bot_status(bot, "DRAINING")
                with self.assertRaisesRegex(PaperPlaneError, code):
                    accept(store, self.strategy, sid)
                row = store.get_position(reserved["position_id"])
                self.assertEqual((row["state"], row["cancel_reason_code"]), ("CANCELLED", reason))
                self.assertNotIn(
                    "PAPER_SIMULATION_OBSERVED",
                    event_types(store, position_id=row["position_id"]),
                )

    def test_stop_bot_cancels_pre_attempt_intents_and_reaches_stopped(self) -> None:
        store = self.store()
        reserved = self.reserve(store, "SIGDEC-VERT-J4")
        stop = apply_operator_command(
            store,
            {
                "command_type": "STOP_BOT",
                "idempotency_key": "IDEM-VERT-J4",
                "bot_instance_id": reserved["bot_instance_id"],
            },
        )
        self.assertEqual(stop["bot_status"], "STOPPED")
        self.assertEqual(stop["cancelled_intents"], [reserved["position_id"]])
        row = store.get_position(reserved["position_id"])
        self.assertEqual((row["state"], row["cancel_reason_code"]), ("CANCELLED", "OPERATOR_STOP"))
        again = accept(store, self.strategy, "SIGDEC-VERT-J4")
        self.assertEqual((again["opened"], again["state"]), (False, "CANCELLED"))
        self.assertFalse(maybe_finish_drain(store, reserved["bot_instance_id"])["changed"])

    def test_close_all_cancels_pre_attempt_and_skips_in_flight(self) -> None:
        store = self.store()
        pending = self.reserve(store, "SIGDEC-VERT-CA-PENDING")
        flying = self.reserve(store, "SIGDEC-VERT-CA-FLYING")
        walk_to(store, flying["position_id"], "SIGNALLED", "INTENT_CREATED", "ATTEMPTING")
        bot = pending["bot_instance_id"]
        sha = build_operations_projection(store)["open_position_set_sha256_by_bot"][bot]
        result = apply_operator_command(
            store,
            {
                "command_type": "REQUEST_CLOSE_ALL",
                "idempotency_key": "IDEM-VERT-CA",
                "bot_instance_id": bot,
                "expected_open_position_set_sha256": sha,
            },
        )
        fanout = {item["position_id"]: item for item in result["fanout"]}
        self.assertEqual(fanout[pending["position_id"]]["state"], "CANCELLED")
        self.assertEqual(
            fanout[flying["position_id"]].get("skipped"),
            "ATTEMPT_IN_FLIGHT_RECONCILE_REQUIRED",
        )
        self.assertEqual(store.get_position(flying["position_id"])["state"], "ATTEMPTING")

    def test_close_position_cancels_a_pre_attempt_intent(self) -> None:
        store = self.store()
        pid = self.reserve(store, "SIGDEC-VERT-CP")["position_id"]
        result = self.close_request(store, pid, "IDEM-VERT-CP")
        self.assertEqual(result["state"], "CANCELLED")
        self.assertEqual(store.get_position(pid)["cancel_reason_code"], "OPERATOR_CANCEL")
        self.assertTrue(self.close_request(store, pid, "IDEM-VERT-CP-2")["applied"])

    def test_retry_never_fills_an_in_flight_attempt(self) -> None:
        for target in ("ATTEMPTING", "UNKNOWN"):
            with self.subTest(state=target):
                store = self.store(f"inflight-{target}.sqlite")
                sid = f"SIGDEC-VERT-FLY-{target}"
                pid = self.reserve(store, sid)["position_id"]
                walk_to(store, pid, "SIGNALLED", "INTENT_CREATED", "ATTEMPTING")
                if target == "UNKNOWN":
                    walk_to(store, pid, "UNKNOWN")
                before = event_types(store, position_id=pid)
                again = accept(store, self.strategy, sid)
                self.assertFalse(again["opened"])
                self.assertTrue(again["reconciliation_required"])
                self.assertEqual(store.get_position(pid)["state"], target)
                self.assertEqual(event_types(store, position_id=pid), before)

    def test_cancel_rules(self) -> None:
        store = self.store()
        open_pid = open_filled(store, self.strategy, "SIGDEC-VERT-CXL-OPEN")
        with self.assertRaisesRegex(PaperPlaneError, "CANCEL_STATE_INVALID:OPEN"):
            store.cancel_entry_intent(open_pid, reason_code="OPERATOR_CANCEL")
        pid = self.reserve(store, "SIGDEC-VERT-CXL-ATT")["position_id"]
        walk_to(store, pid, "SIGNALLED", "INTENT_CREATED", "ATTEMPTING")
        with self.assertRaisesRegex(PaperPlaneError, "CANCEL_REQUIRES_DEFINITIVE_NON_FILL:ATTEMPTING"):
            store.cancel_entry_intent(pid, reason_code="OPERATOR_CANCEL")
        first = store.cancel_entry_intent(pid, reason_code="REJECTED_BEFORE_SEND")
        again = store.cancel_entry_intent(pid, reason_code="REJECTED_BEFORE_SEND")
        self.assertEqual((first["state"], again["state"]), ("CANCELLED", "CANCELLED"))
        self.assertEqual(event_types(store, position_id=pid).count("ENTRY_INTENT_CANCELLED"), 1)
        with self.assertRaisesRegex(PaperPlaneError, "CANCEL_REASON_INVALID"):
            store.cancel_entry_intent(pid, reason_code="NOT_A_REASON")

    def test_cancelled_intent_releases_its_entry_slot(self) -> None:
        store = self.store()
        apply_paper_policy(store, "IDEM-VERT-SLOT-POLICY", max_total_open_positions=1)
        first = self.reserve(store, "SIGDEC-VERT-SLOT-A")
        with self.assertRaisesRegex(PaperPlaneError, "BLOCK_GLOBAL_MAX_OPEN_POSITIONS"):
            accept(store, self.strategy, "SIGDEC-VERT-SLOT-B")
        self.close_request(store, first["position_id"], "IDEM-VERT-SLOT-CLOSE")
        self.assertTrue(accept(store, self.strategy, "SIGDEC-VERT-SLOT-B")["opened"])

    def test_stale_resume_cancels_the_reserved_intent(self) -> None:
        store = self.store()
        pid = self.reserve(store, "SIGDEC-VERT-STALE")["position_id"]
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_STALE"):
            accept(store, self.strategy, "SIGDEC-VERT-STALE", as_of="2026-09-03T12:25:01Z")
        row = store.get_position(pid)
        self.assertEqual((row["state"], row["cancel_reason_code"]), ("CANCELLED", "SIGNAL_EXPIRED"))

    def test_entry_fill_is_bound_to_the_admission(self) -> None:
        store = self.store()
        pid = str(accept(store, self.strategy, "SIGDEC-VERT-BIND")["position_id"])
        base = {"position_id": pid, "entry_unit_price_usd": "1.00", "mode": "PAPER"}
        with self.assertRaisesRegex(PaperPlaneError, "ENTRY_FILL_FEE_MISMATCH"):
            store.apply_paper_entry_fill(entry_gross_notional_usd="100", fee_bps=1, **base)
        with self.assertRaisesRegex(PaperPlaneError, "ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION"):
            store.apply_paper_entry_fill(entry_gross_notional_usd="150", **base)
        filled = store.apply_paper_entry_fill(entry_gross_notional_usd="100", **base)
        self.assertEqual((filled["fee_bps"], filled["entry_fee_usd_dec"]), (10, "0.10"))

    def test_consumers_treat_cancelled_as_settled_without_pnl(self) -> None:
        store = self.store()
        pid = self.reserve(store, "SIGDEC-VERT-PROJ")["position_id"]
        self.close_request(store, pid, "IDEM-VERT-PROJ")
        ops = build_operations_projection(store)
        self.assertNotIn(pid, ops["open_position_ids"])
        self.assertEqual(ops["cancelled_intents"], 1)
        self.assertEqual(ops["known_open_exposure_status"], "EMPTY")
        row = next(item for item in ops["position_rows"] if item["position_id"] == pid)
        self.assertEqual(row["pnl_status"], "NOT_APPLICABLE")
        trading = compose_trading_operations(ROOT, store)
        trace = next(t for t in trading["traces"] if t.get("signal_decision_id") == "SIGDEC-VERT-PROJ")
        self.assertEqual(trace["blocker"], "INTENT_CANCELLED")
        lifecycle = build_lifecycle_projection(
            ROOT,
            paper_plane_store=store,
            research_store=_NoResearch(),
            projected_at=T0,
            git_sha="0" * 40,
        )
        self.assertIn("CANCELLED", {e.get("native_state") for e in lifecycle["entities"]})


def exit_decision(
    position_id: str,
    *,
    exit_id: str = "EXITDEC-VERT-1",
    strategy_version: str = "V1",
    reason_code: str = "VERTICAL_EXIT",
) -> dict[str, Any]:
    return {
        "schema": "smial.exit-decision",
        "schema_version": "1.0",
        "exit_decision_id": exit_id,
        "position_id": position_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": strategy_version,
        "activation_epoch_id": EPOCH,
        "decision_at": "2026-09-03T12:20:00Z",
        "first_reliable_available_at": "2026-09-03T12:19:00Z",
        "action": "EXIT",
        "reason_code": reason_code,
        "evidence_refs": ["sha256:" + "e" * 64],
    }


class DecisionIdentityGateTests(StoreCase):
    """A3 DECISION_IDENTITY_AND_LINEAGE_GATES_V1."""

    def test_as_of_is_required(self) -> None:
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_AS_OF_REQUIRED"):
            accept(self.store(), self.strategy, "SIGDEC-VERT-NOCLOCK", as_of=None)

    def test_future_decision_is_rejected_beyond_skew(self) -> None:
        store = self.store()
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_FROM_FUTURE"):
            accept(store, self.strategy, "SIGDEC-VERT-FUT-3", decision_at="2026-09-03T12:10:03Z")
        self.assertTrue(
            accept(store, self.strategy, "SIGDEC-VERT-FUT-2", decision_at="2026-09-03T12:10:02Z")["opened"]
        )

    def test_one_id_binds_one_body(self) -> None:
        store = self.store()
        self.assertTrue(accept(store, self.strategy, "SIGDEC-VERT-ID")["opened"])
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_IDEMPOTENCY_MISMATCH"):
            accept(store, self.strategy, "SIGDEC-VERT-ID", mint=MINT_B)
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_IDEMPOTENCY_MISMATCH"):
            accept(store, self.strategy, "SIGDEC-VERT-ID", action="NO_ENTER")
        again = accept(store, self.strategy, "SIGDEC-VERT-ID")
        self.assertEqual((again["idempotent"], again["state"]), (True, "OPEN"))
        self.assertEqual(store.get_position("POS-SIG-SIGDEC-VERT-ID")["mint"], MINT)

    def test_exit_decision_version_must_match_the_position(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-XVER")
        v2 = dict(self.strategy, strategy_version="V2")
        with self.assertRaisesRegex(PaperPlaneError, "EXIT_POSITION_VERSION_MISMATCH"):
            accept_exit_decision(
                ROOT,
                store,
                strategy=v2,
                exit_decision=exit_decision(pid, strategy_version="V2"),
                known_activation_epochs=KNOWN_EPOCHS,
            )
        self.assertEqual(store.get_position(pid)["state"], "OPEN")

    def test_strategy_spec_drift_fails_closed(self) -> None:
        store = self.store()
        store.start_bot(self.strategy, mode="PAPER", activation_epoch_id=EPOCH)
        drifted = dict(self.strategy, spec_sha256="0" * 64)
        with self.assertRaisesRegex(PaperPlaneError, "STRATEGY_SPEC_DRIFT"):
            store.start_bot(drifted, mode="PAPER", activation_epoch_id=EPOCH)

    def test_position_lineage_is_queryable_from_the_store(self) -> None:
        store = self.store()
        pid = open_filled(store, self.strategy, "SIGDEC-VERT-LINEAGE")
        accept_exit_decision(
            ROOT,
            store,
            strategy=self.strategy,
            exit_decision=exit_decision(pid),
            known_activation_epochs=KNOWN_EPOCHS,
        )
        row = store.get_position(pid)
        self.assertEqual(row["signal_decision_sha256"], canonical_spec_sha256(signal("SIGDEC-VERT-LINEAGE")))
        self.assertEqual(row["strategy_spec_sha256"], self.strategy["spec_sha256"])
        self.assertEqual((row["reason_code"], row["exit_reason_code"]), ("VERTICAL_ENTER", "VERTICAL_EXIT"))
        events = {
            e["event_type"]: e["payload"]
            for e in store.execution_events()
            if e.get("position_id") == pid
            or (e.get("payload") or {}).get("signal_decision_id") == "SIGDEC-VERT-LINEAGE"
        }
        self.assertEqual(
            events["SIGNAL_DECISION_ACCEPTED"]["evidence_refs"],
            signal("SIGDEC-VERT-LINEAGE")["evidence_refs"],
        )
        self.assertEqual(events["EXIT_DECISION_ACCEPTED"]["exit_decision_id"], "EXITDEC-VERT-1")
        trading = compose_trading_operations(ROOT, store)
        trace = next(t for t in trading["traces"] if t.get("signal_decision_id") == "SIGDEC-VERT-LINEAGE")
        stages = {item["event_type"]: item["stage"] for item in trace["events"]}
        self.assertEqual(stages["EXIT_DECISION_ACCEPTED"], "POSITION")


class ReadFreshnessTests(StoreCase):
    """A4: public owner reads of mutable SQLite, not injected store fixtures."""

    def factory_root(self, name: str) -> Path:
        root = self.dir / name
        for relative in (
            "catalog/schemas/strategy_version_v1_1.schema.json",
            "catalog/schemas/signal_decision_v1.schema.json",
            "catalog/schemas/exit_decision_v1.schema.json",
            "configs/trading_runtime_policy_v1.yaml",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        strategy = dict(self.strategy)
        strategy["notional_policy"] = dict(strategy["notional_policy"], notional_usd=30)
        strategy.pop("spec_sha256", None)
        strategy["spec_sha256"] = canonical_spec_sha256(strategy)
        self.strategy = validate_and_hash_strategy(ROOT, strategy)
        target = root / "configs/strategies/audit.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(self.strategy), encoding="utf-8")
        return root

    def app(self, root: Path) -> FactoryApplication:
        return FactoryApplication(root=root, research_data_root=root / "empty-rdp", spec_relative="unused.yaml")

    @staticmethod
    def policy(store: PaperPlaneStore, cap: int, key: str) -> dict[str, Any]:
        candidate = {
            "new_entries_enabled": True, "global_entry_notional_cap_usd": str(cap),
            "max_total_open_positions": 10, "max_total_open_notional_usd": "300",
            "default_strategy_max_open_positions": 10,
            "default_strategy_max_open_notional_usd": "300",
            "max_open_positions_per_mint": 10, "max_open_notional_per_mint_usd": "300",
            "strategy_overrides": {},
        }
        preview = check_policy(store, mode="PAPER", candidate_raw=candidate)
        apply_policy(
            ROOT, store, mode="PAPER", candidate_raw=candidate,
            expected_current_sha256=preview["expected_current_sha256"], idempotency_key=key,
            owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
            reason="DISPOSABLE_SYNTHETIC_AUTHORITY_ONLY",
        )
        return show_policy(store, "PAPER")

    @staticmethod
    def inventory(root: Path) -> dict[str, str]:
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file()}

    @staticmethod
    def business_hash(store: PaperPlaneStore) -> str:
        # Independent SQL dump covers schema and every business table, not
        # merely total_changes on the writer or a single position.
        return hashlib.sha256("\n".join(store._conn.iterdump()).encode()).hexdigest()

    def test_public_live_wal_position_policy_and_next_read_two_repetitions(self) -> None:
        self.observations: list[dict[str, Any]] = []
        for index in range(2):
            with self.subTest(repetition=index + 1):
                root = self.factory_root(f"public-{index}")
                db = root / "local/factory_v1/paper_plane_state.sqlite"
                writer = PaperPlaneStore(db)
                self._stores.append(writer)
                writer._conn.execute("PRAGMA wal_autocheckpoint=0")
                self.policy(writer, 30, f"IDEM-FRESH-{index}-30")
                pid = open_filled(writer, self.strategy, f"SIGDEC-FRESH-{index}")
                admitted = dict(writer.get_position(pid))
                writer._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                writer.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=None, mode="PAPER", unresolved=True)
                current = self.policy(writer, 20, f"IDEM-FRESH-{index}-20")
                self.assertFalse(writer._conn.in_transaction)
                before = self.inventory(root)
                business_before = [dict(row) for row in writer._conn.execute("SELECT * FROM positions")]
                business_hash_before = self.business_hash(writer)
                app = self.app(root)
                try:
                    view = app.trading_operations_projection()
                    row = next(row for row in view["operations"]["position_rows"] if row["position_id"] == pid)
                    self.assertEqual(row["state"], "UNRESOLVED")
                    envelope = view["runtime_envelope"]["modes"]["PAPER"]
                    self.assertEqual(envelope["policy_sha256"], current["policy_sha256"])
                    self.assertEqual(envelope["revision"], 2)
                    self.assertEqual(str(envelope["global_entry_notional_cap_usd"]), "20")
                    after = self.inventory(root)
                    sidecars = {"local/factory_v1/paper_plane_state.sqlite-wal",
                                "local/factory_v1/paper_plane_state.sqlite-shm"}
                    self.assertEqual({k: v for k, v in after.items() if k not in sidecars},
                                     {k: v for k, v in before.items() if k not in sidecars})
                    forbidden_created = sorted(set(after) - set(before) - sidecars)
                    self.assertEqual(forbidden_created, [])
                    self.assertEqual([dict(row) for row in writer._conn.execute("SELECT * FROM positions")], business_before)
                    business_hash_after = self.business_hash(writer)
                    self.assertEqual(business_hash_after, business_hash_before)
                    self.assertEqual(writer.get_position(pid)["admitted_entry_notional_usd_dec"], admitted["admitted_entry_notional_usd_dec"])
                    further = self.policy(writer, 15, f"IDEM-FRESH-{index}-15")
                    next_view = app.trading_operations_projection()
                    self.assertEqual(next_view["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"], further["policy_sha256"])
                    self.assertTrue(db.with_name(db.name + "-wal").is_file())
                    self.observations.append({
                        "repetition": index + 1, "position_state": row["state"],
                        "policy_revision": envelope["revision"],
                        "current_cap": envelope["global_entry_notional_cap_usd"],
                        "writer_policy_sha256": current["policy_sha256"],
                        "reader_policy_sha256": envelope["policy_sha256"],
                        "frozen_admission": writer.get_position(pid)["admitted_entry_notional_usd_dec"],
                        "business_sha256_before_read": business_hash_before,
                        "business_sha256_after_read": business_hash_after,
                        "business_unchanged": True, "forbidden_created_files": forbidden_created,
                        "next_read_revision": next_view["runtime_envelope"]["modes"]["PAPER"]["revision"],
                        "next_read_hash": next_view["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"],
                        "writer_open": True, "wal_present": True,
                    })
                finally:
                    app._close_paper_plane_readonly()

    def test_one_projection_snapshot_and_next_request_freshness(self) -> None:
        root = self.factory_root("snapshot")
        writer = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
        self._stores.append(writer)
        first = self.policy(writer, 30, "IDEM-SNAPSHOT-30")
        app = self.app(root)
        from solana_alpha_lab.factory import trading_operations
        original = trading_operations.build_operations_projection

        def commit_between_reads(reader: PaperPlaneStore) -> dict[str, Any]:
            operations = original(reader)  # Establish the read snapshot.
            self.policy(writer, 20, "IDEM-SNAPSHOT-20")
            return operations

        try:
            with patch.object(trading_operations, "build_operations_projection", commit_between_reads):
                view = app.trading_operations_projection()
            self.assertEqual(view["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"], first["policy_sha256"])
            current = show_policy(writer, "PAPER")
            next_view = app.trading_operations_projection()
            self.assertEqual(next_view["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"], current["policy_sha256"])
            self.assertIsNone(app._paper_plane_readonly)
        finally:
            app._close_paper_plane_readonly()

    def test_lifecycle_and_http_read_the_same_live_position_owner(self) -> None:
        from test_trading_operations_workbench_v2 import isolated_factory_root, _get
        root = isolated_factory_root(self.dir / "public-consumers")
        for relative in ("configs/owner_lifecycle_projection_v1.yaml",
                         "catalog/schemas/owner_lifecycle_projection_v1.schema.json"):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        db = root / "local/factory_v1/paper_plane_state.sqlite"
        writer = PaperPlaneStore(db)
        self._stores.append(writer)
        pid = open_filled(writer, self.strategy, "SIGDEC-FRESH-CONSUMERS")
        writer._conn.execute("PRAGMA wal_autocheckpoint=0")
        writer._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=None, mode="PAPER", unresolved=True)
        before_hash = self.business_hash(writer)
        app = FactoryApplication(root=root, research_data_root=root / "empty-rdp")
        try:
            projection = app.lifecycle_projection()
            position = next(row for row in projection["entities"] if row["entity_id"] == pid)
            self.assertEqual(position["native_state"], "UNRESOLVED")
            body = _get(app, "/operations")
            self.assertIn("UNRESOLVED", body)
            self.assertIn(pid, body)
            self.assertEqual(self.business_hash(writer), before_hash)
        finally:
            app._close_paper_plane_readonly()

    def test_read_failure_does_not_reuse_success_or_infer_empty_runtime(self) -> None:
        root = self.factory_root("read-error")
        writer = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
        self._stores.append(writer)
        open_filled(writer, self.strategy, "SIGDEC-READ-ERROR")
        app = self.app(root)
        try:
            self.assertEqual(app.trading_operations_projection()["source_status"], "PRESENT")
            before = self.inventory(root)
            with patch.object(PaperPlaneStore, "positions", side_effect=sqlite3.OperationalError("SYNTHETIC_READ_FAILURE")):
                failed = app.trading_operations_projection()
                self.assertEqual(failed["source_status"], "UNAVAILABLE")
                self.assertIsNone(failed["operations"])
                self.assertEqual(failed["runtime_envelope"]["modes"], {})
                self.assertIn("RUNTIME_SOURCE_UNAVAILABLE", {row["code"] for row in failed["attention"]})
                economics = app.economics_projection()
                self.assertEqual(economics["source_status"], "UNAVAILABLE")
                self.assertIsNone(economics["reconciled_net_pnl_usd"])
                with self.assertRaises(ApplicationError) as raised:
                    app.operations_projection()
                self.assertEqual(raised.exception.code, "RUNTIME_SOURCE_UNAVAILABLE")
            self.assertEqual(self.inventory(root), before)
            self.assertEqual(app.trading_operations_projection()["source_status"], "PRESENT")
        finally:
            app._close_paper_plane_readonly()

    def test_overlapping_http_gets_do_not_close_each_others_reader(self) -> None:
        from test_trading_operations_workbench_v2 import isolated_factory_root, _get
        from solana_alpha_lab.factory import trading_operations
        root = isolated_factory_root(self.dir / "overlapping-get")
        writer = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
        self._stores.append(writer)
        pid = open_filled(writer, self.strategy, "SIGDEC-OVERLAP")
        self.policy(writer, 30, "IDEM-OVERLAP-30")
        writer._conn.execute("PRAGMA wal_autocheckpoint=0")
        writer._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=None, mode="PAPER", unresolved=True)
        current = self.policy(writer, 20, "IDEM-OVERLAP-20")
        before = self.business_hash(writer)
        app = FactoryApplication(root=root, research_data_root=root / "empty-rdp")
        barrier = threading.Barrier(2)
        first_read_ready = threading.Event()
        original = trading_operations.build_operations_projection
        original_public = app.trading_operations_projection
        observed, bodies, errors, readers = [], [], [], []

        def overlapping_projection(reader: PaperPlaneStore) -> dict[str, Any]:
            readers.append(reader)
            first_read_ready.set()
            barrier.wait(timeout=10)
            return original(reader)

        def capture_public(**kwargs: Any) -> dict[str, Any]:
            view = original_public(**kwargs)
            observed.append(view)
            return view

        def request(index: int) -> None:
            try:
                if index == 1 and not first_read_ready.wait(timeout=10):
                    raise RuntimeError("FIRST_GET_DID_NOT_ENTER_READ")
                bodies.append(_get(app, "/operations"))
            except Exception as exc:
                errors.append(type(exc).__name__)

        with patch.object(trading_operations, "build_operations_projection", overlapping_projection), \
             patch.object(app, "trading_operations_projection", capture_public):
            threads = [threading.Thread(target=request, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(observed), 2)
        self.assertEqual(len({id(reader) for reader in readers}), 2)
        for reader in readers:
            with self.assertRaises(sqlite3.ProgrammingError):
                reader._conn.execute("SELECT 1")
        self.assertEqual([view["source_status"] for view in observed], ["PRESENT", "PRESENT"])
        for view in observed:
            self.assertEqual(view["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"], current["policy_sha256"])
            self.assertEqual(next(row for row in view["operations"]["position_rows"] if row["position_id"] == pid)["state"], "UNRESOLVED")
        self.assertTrue(all(pid in body and "UNRESOLVED" in body for body in bodies))
        self.assertEqual(self.business_hash(writer), before)
        further = self.policy(writer, 15, "IDEM-OVERLAP-15")
        self.assertEqual(app.trading_operations_projection()["runtime_envelope"]["modes"]["PAPER"]["policy_sha256"], further["policy_sha256"])
        app._close_paper_plane_readonly()

    def test_non_wal_compatibility_is_readonly_without_business_writes(self) -> None:
        root = self.factory_root("non-wal")
        db = root / "local/factory_v1/paper_plane_state.sqlite"
        writer = PaperPlaneStore(db)
        open_filled(writer, self.strategy, "SIGDEC-NON-WAL")
        writer._conn.execute("PRAGMA journal_mode=DELETE")  # Fixture preparation, before read.
        writer.close()
        before = self.inventory(root)
        app = self.app(root)
        try:
            self.assertEqual(app.trading_operations_projection()["source_status"], "PRESENT")
            reader = app.existing_paper_plane()
            with self.assertRaises(sqlite3.OperationalError):
                reader._conn.execute("CREATE TABLE forbidden_business_write(value)")
            self.assertEqual(self.inventory(root), before)
        finally:
            app._close_paper_plane_readonly()

    def test_os_denies_source_access_without_bootstrap_or_stale_fallback(self) -> None:
        root = self.factory_root("denied")
        db = root / "local/factory_v1/paper_plane_state.sqlite"
        writer = PaperPlaneStore(db)
        open_filled(writer, self.strategy, "SIGDEC-DENIED")
        writer._conn.execute("PRAGMA journal_mode=DELETE")
        writer.close()
        before = self.inventory(root)
        app = self.app(root)
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                              wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
                kernel.CreateFileW.restype = wintypes.HANDLE
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel.CloseHandle.restype = wintypes.BOOL
                handle = kernel.CreateFileW(str(db), 0x80000000, 0, None, 3, 0, None)
                self.assertNotEqual(handle, wintypes.HANDLE(-1).value, ctypes.get_last_error())
                try:
                    with self.assertRaises(PermissionError):
                        db.read_bytes()
                    failed = app.trading_operations_projection()
                finally:
                    self.assertTrue(kernel.CloseHandle(handle))
            else:
                original_mode = db.stat().st_mode
                db.chmod(0)
                try:
                    with self.assertRaises(PermissionError):
                        db.read_bytes()
                    failed = app.trading_operations_projection()
                finally:
                    db.chmod(original_mode)
            self.assertEqual(failed["source_status"], "UNAVAILABLE")
            self.assertIsNone(failed["operations"])
            self.assertEqual(failed["runtime_envelope"]["modes"], {})
            self.assertEqual(self.inventory(root), before)
        finally:
            app._close_paper_plane_readonly()

    def test_missing_and_corrupt_source_never_bootstraps_or_all_clears(self) -> None:
        for kind in ("missing-root", "missing-db", "corrupt"):
            with self.subTest(source=kind):
                root = self.dir / kind if kind == "missing-root" else self.factory_root(kind)
                db = root / "local/factory_v1/paper_plane_state.sqlite"
                if kind == "corrupt":
                    db.parent.mkdir(parents=True)
                    db.write_bytes(b"not an sqlite database")
                before = self.inventory(root)
                app = self.app(root)
                try:
                    view = app.trading_operations_projection()
                    self.assertEqual(view["source_status"], "UNAVAILABLE" if kind == "corrupt" else "NOT_PRESENT")
                    self.assertIsNone(view["operations"])
                    self.assertEqual(view["runtime_envelope"]["modes"], {})
                    self.assertEqual(self.inventory(root), before)
                    if kind == "missing-root":
                        self.assertFalse(root.exists())
                finally:
                    app._close_paper_plane_readonly()


if __name__ == "__main__":
    unittest.main()
