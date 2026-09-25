---
task_id: PAPER_PLANE_WRITE_INTEGRITY_V1
task_version: '1.0'
status: READY
as_of: '2026-09-26'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
  - DIRECT_CODEX_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ae678372f2a96fbc20c519c23905ae5c44332458
  expected_upstream: origin/main
  expected_upstream_oid: ae678372f2a96fbc20c519c23905ae5c44332458
  expected_branch: cursor/paper-plane-write-integrity-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make every PaperPlane state change atomic with the lineage events that
  describe it and conditional on the state it read; make operator commands
  atomic with their idempotency record; return execution events in causal
  order. Series PAPER_SHADOW_EXECUTION_INTEGRITY atom 1 of 5.
managed_write_set:
  - docs/tasks/PAPER_PLANE_WRITE_INTEGRITY_V1.md
  - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/paper_shadow_commands.py
  - tests/test_paper_shadow_execution_integrity_vertical_v1.py
  - configs/execution_domain_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/paper_plane_write_integrity/a1_owner_readout_v1.md
  - docs/evidence/paper_plane_write_integrity/a1_delivery_completion_evidence_v1.json
  - docs/evidence/paper_plane_write_integrity/a1_delivery_independent_review_v1.json
  - docs/evidence/paper_plane_write_integrity/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_API_RPC_WSS_REQUIRED
  - CREDENTIAL_VALUE_REQUIRED
  - VPS_OR_DEPLOY_MUTATION_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - WALLET_SIGNER_TRANSACTION_REQUIRED
  - SCHEMA_CHANGE_REQUIRED
  - BEHAVIOR_CHANGE_BEYOND_ATOMICITY
  - SECOND_RUNTIME_STORE
  - TEST_DELETION_SKIP_OR_WEAKENING
  - WRITE_SET_EXPANSION_REQUIRED
  - BASE_DRIFT_REQUIRES_REPLAN
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/paper_plane_write_integrity/a1_delivery_completion_evidence_v1.json
      - docs/evidence/paper_plane_write_integrity/a1_delivery_independent_review_v1.json
      - docs/evidence/paper_plane_write_integrity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# PAPER_PLANE_WRITE_INTEGRITY_V1
`SPEC_ROUTE=DESIGN_SPEC`: design in `docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md`
§3 and §5 (added by this atom); this file is the exact task contract. Delivery mode:
`VERTICAL_CAPABILITY_REPAIR_LOOP`, one atom, one PR. Series atom 1 of 5. Model effort: `SOL_XHIGH`.
## DECISION_DELTA
Every PaperPlane state change commits together with the events that describe it and only if the state
it read is still current; an operator command commits together with its idempotency record;
`execution_events()` returns insertion order.
## UNCERTAINTY_REMOVED
Whether the single SQLite PAPER/SHADOW plane stays truthful with two concurrent writers (Workbench
operator + a runner) and after a crash between a state write and its event.
## CAPABILITY_OR_EVIDENCE
A deterministic race (operator close vs exit fill) ends `RECONCILED` with exactly one exit and one
reconciliation event (audit: 55/200 regressed to `EXIT_REQUIRED` with PnL kept); an injected crash after
the state write leaves no partial state (audit: `RECONCILED` without exit events, unrecoverable); events
come back in causal order (audit: random inside one second).
## STOP
`PAPER_PLANE_WRITE_INTEGRITY_PASS_READY_FOR_MERGE_GATE`
## NEXT
`PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1` (series atom 2) under its own contract.
## Task Outcome Brief
- Owner decision: repair write integrity at the primitive level. No schema change, no new store, no
  dependency, no caller-visible behavior change except atomicity, ordering and the new `STALE_STATE` code.
- Named consumers: the future v1.1 runner writing next to Workbench operator commands; Trading Operations
  traces that read `execution_events`; atoms A2–A5, which build on these primitives.
- Cheapest falsifier (≤ 20 min): the race test in 3.2 stays red after 3.3, or an existing execution-domain
  test fails because a caller relied on non-atomic behavior.
- Terminal outcomes: `PAPER_PLANE_WRITE_INTEGRITY_PASS_READY_FOR_MERGE_GATE`,
  `STOP BEHAVIOR_CHANGE_BEYOND_ATOMICITY`, `STOP WRITE_SET_EXPANSION_REQUIRED`,
  `STOP BASE_DRIFT_REQUIRES_REPLAN`.
- User-visible result: Trading Operations traces list events in causal order; nothing else visible.
- Evidence budget: focused tests; one local stochastic run with 500 iterations recorded in the owner
  readout; at most two exact-head CI iterations.
- Replan trigger: a deadlock or `database is locked` under the race tests that needs more than
  `BEGIN IMMEDIATE` plus `busy_timeout`.
## 1. Forensic truth (audit 2026-09-25/26, reproduced independently 2/2)
- Lost update: `PaperPlaneStore.transition()` runs `SELECT` then `UPDATE` in autocommit without a state
  condition; `apply_operator_command` has no transaction. `REQUEST_CLOSE_POSITION` racing
  `apply_paper_exit_fill` regressed `RECONCILED → EXIT_REQUIRED` in 55/200 natural trials (hook 2/2); a
  second exit fill then duplicated `PAPER_EXIT_OBSERVED` and `RECONCILIATION`. The opposite interleaving
  aborted the fill 21/200 because `apply_paper_exit_fill` reads `state0` outside its transaction.
- Crash window: `accept_signal_decision` appends `EXECUTION_INTENT_CREATED` and `POSITION_TRANSITION`
  after the fill commit; `apply_paper_exit_fill` appends `PAPER_EXIT_OBSERVED` and `RECONCILIATION` after
  its commit; `apply_paper_entry_fill` has no transaction at all. An exception in that window left
  `RECONCILED` without exit events (retry: `EXIT_FILL_STATE_INVALID:RECONCILED`) and `OPEN` without
  `EXECUTION_INTENT_CREATED` forever.
- Ordering: `execution_events()` orders by `created_at, event_id`; `event_id` is a random uuid, so events
  inside one second come back in random order; Trading Operations fills trace fields first-wins.
## 2. Operational invariants
- W1 Atomic transition: `transition()` runs inside `BEGIN IMMEDIATE` (its own or the enclosing one),
  re-reads the state inside it and writes `WHERE position_id = ? AND state = ?`; rowcount ≠ 1 →
  `PaperPlaneError("STALE_STATE:<from>-><to>")`.
- W2 Atomic lineage: every event describing a state change is appended in the same transaction.
- W3 Atomic commands: idempotency lookup, effects, events and `record_operator_command` are one transaction.
- W4 Causal order: `execution_events()` returns `ORDER BY rowid`.
- W5 Behavior preservation: same results and error codes on every non-concurrent, non-crash path; legacy
  v1.0 paths (`run_commissioning`, `run_shadow_tick`, `fill_paper`, `observe_shadow`) keep working.
- W6 No schema change, no test deletion, skip or weakening.
## 3. Execution
### 3.0 Hygiene and binding
- One fresh worktree from the current `origin/main`, opened as the only root. If `origin/main` ≠
  `expected_base`: when the new commits touch none of this write set, set `expected_base` and
  `expected_upstream_oid` to the new head; otherwise `STOP BASE_DRIFT_REQUIRES_REPLAN`.
- First commit: this contract as `docs/tasks/PAPER_PLANE_WRITE_INTEGRITY_V1.md` and the series design as
  `docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md` (both copied unchanged from the pack).
- Run local tests alone (one test process per checkout).
- Python: `uv run --locked --managed-python python -B` (or the repository `.venv` Python with `-B`).
### 3.1 Baseline, before any edit
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_accounting_and_control_v1 tests.test_trading_runtime_admission_concurrency_v1 tests.test_factory_strategy_execution_boundary_v1 tests.test_trading_operations_workbench_v2
```
Record counts and durations.
### 3.2 Red: create `tests/test_paper_shadow_execution_integrity_vertical_v1.py`
Append the module path to `required_fast_test_modules` in `configs/execution_domain_v1.json` (a test that
imports `paper_plane` must be declared there). Later atoms add classes to this module; keep the helpers
generic.
```python
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
```
Run `uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1`.
Expected red: the race test (`EXIT_REQUIRED` ≠ `RECONCILED`), the stochastic test, all four crash tests
(partial state survives), the command test, and the order test. The same-signal test is a regression
guard and may already pass.
### 3.3 Minimal fix: `src/solana_alpha_lab/factory/paper_plane.py`
1. Constant near `TRANSITIONS`: `CLOSING_STATES = frozenset({"CLOSED", "RECONCILED"})`.
2. `transition()`:
```python
    def transition(
        self, position_id: str, to_state: str, *, commit: bool = True
    ) -> dict[str, Any]:
        # `commit` is kept for call-site compatibility; every transition is atomic.
        with self.immediate_write():
            row = self._conn.execute(
                "SELECT state FROM positions WHERE position_id = ?", (position_id,)
            ).fetchone()
            if row is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            current = str(row["state"])
            if to_state not in TRANSITIONS.get(current, set()):
                raise PaperPlaneError(f"ILLEGAL_TRANSITION:{current}->{to_state}")
            closed_at = _now() if to_state in CLOSING_STATES else None
            cursor = self._conn.execute(
                """
                UPDATE positions SET state = ?, closed_at = COALESCE(?, closed_at)
                WHERE position_id = ? AND state = ?
                """,
                (to_state, closed_at, position_id, current),
            )
            if cursor.rowcount != 1:
                raise PaperPlaneError(f"STALE_STATE:{current}->{to_state}")
            updated = self.get_position(position_id)
        assert updated is not None
        return updated
```
3. `apply_paper_entry_fill`: keep the signature; move the whole body after the mode check under
   `with self.immediate_write():` (read, `ATTEMPTING → OPEN` transition, economics UPDATE and
   `PAPER_SIMULATION_OBSERVED` / `SHADOW_EXECUTABLE_OBSERVED` append); return after the block.
4. `apply_paper_exit_fill`: one transaction for everything, reading the position inside it:
```python
    def apply_paper_exit_fill(
        self,
        *,
        position_id: str,
        exit_unit_price_usd: str | None,
        mode: str,
        unresolved: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            state0 = str(position["state"])
            if state0 == "RECONCILED":
                raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{state0}")

            def _advance_to_exiting(current: dict[str, Any]) -> dict[str, Any]:
                state = str(current["state"])
                if state in {"OPEN", "PARTIAL", "UNKNOWN"}:
                    current = self.transition(position_id, "EXIT_REQUIRED")
                    state = str(current["state"])
                if state == "EXIT_REQUIRED":
                    current = self.transition(position_id, "EXITING")
                return current

            if unresolved or exit_unit_price_usd is None:
                if state0 not in {"OPEN", "PARTIAL", "UNKNOWN", "EXIT_REQUIRED", "EXITING", "UNRESOLVED"}:
                    raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{state0}")
                position = _advance_to_exiting(position)
                if str(position["state"]) == "EXITING":
                    position = self.transition(position_id, "UNRESOLVED")
                elif str(position["state"]) != "UNRESOLVED":
                    raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{position['state']}")
                self._conn.execute(
                    """
                    UPDATE positions
                    SET pnl_evidence_class = NULL,
                        realized_gross_pnl_usd_dec = NULL,
                        realized_net_pnl_usd_dec = NULL
                    WHERE position_id = ?
                    """,
                    (position_id,),
                )
                self.append_execution_event(
                    event_type="RECONCILIATION",
                    bot_instance_id=str(position["bot_instance_id"]),
                    position_id=position_id,
                    payload={
                        **_identity_fields(position),
                        "result": "UNRESOLVED",
                        "mode": mode,
                        "pnl_status": "UNKNOWN",
                    },
                )
                updated = self.get_position(position_id)
                assert updated is not None
                return updated

            # Priced branch: keep the current entry-field checks and Decimal formulas verbatim
            # (EXIT_FILL_REQUIRES_ENTRY / _ENTRY_NOTIONAL / _ENTRY_FEE, exit_gross, exit_fee, gross,
            # net, evidence), then the current transitions (UNRESOLVED|CLOSED -> RECONCILED, else
            # advance -> CLOSED -> RECONCILED), the current UPDATE, and the two current event
            # appends (PAPER_EXIT_OBSERVED | SHADOW_EXIT_EXECUTABLE_OBSERVED, then RECONCILIATION)
            # - all inside this same `with` block.
            ...
            updated = self.get_position(position_id)
        assert updated is not None
        return updated
```
   Remove the old inner `with self.immediate_write()` blocks and the `commit=False` arguments (harmless,
   but now misleading).
5. `apply_exit_decision`: wrap from `self.get_position(position_id)` to the final read in
   `with self.immediate_write():`.
6. `record_position_mark`, `set_entries_paused`, `set_bot_status`: wrap each body in
   `with self.immediate_write():` (they nest inside commands and admission).
7. `execution_events()`: `SELECT * FROM execution_events ORDER BY rowid`.
8. `accept_signal_decision`, the fill tail (replace from `signal_kind = ...` to `refreshed = ...`):
```python
    signal_kind = "SHADOW_EXECUTABLE" if mode == "SHADOW" else "SIMULATED_FILL"
    with store.immediate_write():
        before = store.get_position(position_id)
        filled_now = before is None or str(before["state"]) != "OPEN"
        opened_id, realized = store.fill_paper_from_signal(
            bot_instance_id=bot_instance_id,
            signal_decision=decision,
            notional_usd=admitted_notional,
            signal_kind=signal_kind,
        )
        if filled_now:
            store.append_execution_event(...)  # EXECUTION_INTENT_CREATED, payload unchanged
            store.append_execution_event(...)  # POSITION_TRANSITION, payload unchanged
    refreshed = store.get_position(opened_id)
```
### 3.4 Minimal fix: `src/solana_alpha_lab/factory/paper_shadow_commands.py`
```python
def apply_operator_command(
    store: PaperPlaneStore,
    command: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply one idempotent operator command atomically with its record."""

    command_type = str(command["command_type"])
    idempotency_key = str(command["idempotency_key"])
    if not idempotency_key:
        raise PaperPlaneError("COMMAND_IDEMPOTENCY_KEY_REQUIRED")
    with store.immediate_write():
        return _apply_operator_command_locked(store, command, command_type, idempotency_key)
```
Move the current body (from `existing = store.get_operator_command(...)` to the final `return`) unchanged
into `_apply_operator_command_locked(store, command, command_type, idempotency_key)`. Wrap the body of
`maybe_finish_drain` in `with store.immediate_write():`.
### 3.5 Focused green and proofs (alone)
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_accounting_and_control_v1 tests.test_trading_runtime_admission_concurrency_v1 tests.test_factory_strategy_execution_boundary_v1 tests.test_trading_runtime_policy_v1 tests.test_trading_operations_workbench_v2 tests.test_risk_and_economics_v1 tests.test_owner_operations_cockpit_v1 tests.test_early_state_to_paper_vertical_slice tests.test_factory_unattended_shadow_vertical_slice tests.test_execution_domain_modularity_and_fast_ci_v1
```
Stochastic proof for the readout (not CI):
```text
PAPER_PLANE_RACE_ITERATIONS=500 uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1.WriteIntegrityTests.test_close_vs_exit_race_never_regresses_or_duplicates
```
(PowerShell: `$env:PAPER_PLANE_RACE_ITERATIONS = "500"` first.) Expected 0 failures. Record wall time.
### 3.6 Durable truth and propagation
- Design file: set §5 status to `A1 MERGED` only after merge (in the readout); in this PR keep the text.
- Catalog: register the task contract, the design document, the vertical test module and the evidence
  trio in `catalog/assets/core.yaml`, mirroring the entries of `PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1`
  (grep its asset ids); then
```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <expected_base>
```
- Re-pin `docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json` only if preflight-push reports
  its shadow pin. Never hand-edit derived hashes.
### 3.7 Review and finish
Isolated critics on the final inventory. The architecture critic attacks: (1) can any path still write a
state without holding the write lock (search every `UPDATE positions` and every `transition(` caller);
(2) can nested `immediate_write` swallow a rollback (exception inside a nested block must abort the outer
transaction); (3) deadlock or starvation between two stores (`busy_timeout=5000`, lock order); (4) do
legacy v1.0 paths behave identically; (5) does `ORDER BY rowid` survive backup/restore by file copy;
(6) what passes every test yet breaks research validity: an event order change that alters a projection
field (first-wins fill in Trading Operations) — prove the projection output is unchanged on the
accounting fixtures. Then Factory Fit / Product Horizon (`CAPABILITY_RADAR_NOW=NONE` expected), owner
readout in Russian with the before/after table, evidence, `bind-evidence --apply` and `--verify`,
`preflight-push`, push, PR.
## 4. Vertical Capability Repair Loop
```text
bind + baseline (3.1)
-> red vertical tests (3.2): race, stochastic, 4 crash windows, command, order
-> minimal fix (3.3, 3.4)
-> focused green + execution-domain modules (3.5)
-> stochastic proof N=500 (0 failures) -> readout
   |- red persists or new deadlock -> one repair iteration inside W1..W4 -> re-run 3.5
   '- still failing -> STOP BEHAVIOR_CHANGE_BEYOND_ATOMICITY (report the minimized case)
-> catalog + harness_sync -> isolated review -> finish -> bind -> preflight-push -> ONE PR
-> exact-head CI (validate-execution runs the vertical module on real runners)
-> merge-readiness -> owner phrase -> guarded merge -> post-merge readback
```
## 5. Definition of Done
1. The vertical module is green; the race test ends `RECONCILED` with one `PAPER_EXIT_OBSERVED` and one
   `RECONCILIATION`; the four crash tests leave the pre-call state; the order test matches exactly.
2. Stochastic proof: 500 iterations, 0 failures, recorded in the readout.
3. All modules in 3.5 green; zero deleted, skipped or weakened tests; no schema change.
4. `configs/execution_domain_v1.json` declares the new module; exact-head CI green.
5. Trading Operations projection output on the accounting fixtures is unchanged apart from event order.
## 6. Non-goals
New states, cancel semantics, stop behavior (A2); decision gates and lineage columns (A3); readonly
freshness (A4); attempts (A5); performance tuning; changing `busy_timeout`; Workbench changes.
## 7. Rollback and limitations
Rollback: revert the merge commit. No persisted-format change. Limitation: writers wait up to
`busy_timeout` (5 s) behind a long transaction; no current path holds the lock longer than one fill.
## 8. Final return
```yaml
capability: PAPER_PLANE_WRITE_INTEGRITY_V1
base: <40hex>
head: <40hex>
red_before_fix: [race, stochastic, crash_exit, crash_unresolved, crash_entry, crash_intent, command, order]
green_after_fix: true
stochastic_proof: {iterations: 500, failures: 0, seconds: <s>}
execution_domain_modules: {passed: <n>, failed: 0}
schema_changed: false
tests_weakened: 0
ci: {exact_head_run: <id>, result: success}
pr: <url>
```
