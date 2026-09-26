---
task_id: PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1
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
  - OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b6ab5f699ad2b2bee3286171ad2728e1bcee1638
  expected_upstream: origin/main
  expected_upstream_oid: b6ab5f699ad2b2bee3286171ad2728e1bcee1638
  expected_branch: cursor/paper-shadow-entry-intent-integrity-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Give entry intents an honest lifecycle: a non-fill terminal CANCELLED,
  operator stops that dominate resumes of admitted but unattempted intents,
  no auto-fill of ATTEMPTING/UNKNOWN on retry, drains that finish without a
  fill claim, entry fills bounded by the admission, and one source of truth
  for lifecycle state sets. Series PAPER_SHADOW_EXECUTION_INTEGRITY atom 2 of 5.
managed_write_set:
  - docs/tasks/PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1.md
  - docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/paper_shadow_commands.py
  - src/solana_alpha_lab/factory/paper_shadow_operations.py
  - src/solana_alpha_lab/factory/trading_operations.py
  - tests/test_paper_shadow_execution_integrity_vertical_v1.py
  - tests/test_paper_shadow_accounting_and_control_v1.py
  - tests/test_trading_operations_workbench_v2.py
  - docs/contracts/trading_runtime_policy_v1.md
  - docs/contracts/risk_and_economics_v1.md
  - docs/contracts/trading_operations_workbench_v2.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/paper_shadow_entry_intent_integrity/a1_owner_readout_v1.md
  - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_completion_evidence_v1.json
  - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_independent_review_v1.json
  - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_factory_fit_v1.json
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
  - REAL_FILL_OR_NETRETURN_CLAIM
  - SECOND_POSITION_MODEL
  - OPEN_RISK_STATES_SEMANTICS_CHANGE
  - LIFECYCLE_VOCABULARY_OWNER_DECISION_CHANGED
  - A1_NOT_MERGED
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
      - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_completion_evidence_v1.json
      - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_independent_review_v1.json
      - docs/evidence/paper_shadow_entry_intent_integrity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1
`SPEC_ROUTE=DESIGN_SPEC`: design in `docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md`
§4 and §6; this file is the exact task contract. Delivery mode: `VERTICAL_CAPABILITY_REPAIR_LOOP`, one
atom, one PR. Series atom 2 of 5; requires A1 (`PAPER_PLANE_WRITE_INTEGRITY_V1`) merged. Model effort:
`SOL_XHIGH` (lifecycle contract).
## DECISION_DELTA
An admitted entry intent reaches `OPEN` only through a non-stopped, admission-bounded fill; every intent
that does not fill ends `CANCELLED` with a reason; retries never fill a possibly-submitted attempt; a stop
drains to `STOPPED` without a fill claim.
## UNCERTAINTY_REMOVED
Whether operator control is absolute for unsubmitted intents and whether the lifecycle can end an intent
honestly without inventing a fill.
## CAPABILITY_OR_EVIDENCE
The audit's stop-bypass matrix (6/6 reached `OPEN`) turns into 0/6; J4 (`STOP_BOT` with a reserved intent)
reaches `STOPPED`; retries of `ATTEMPTING`/`UNKNOWN` answer `reconciliation_required`; fee and notional
overrides at fill are rejected.
## STOP
`PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_PASS_READY_FOR_MERGE_GATE`
## NEXT
`DECISION_IDENTITY_AND_LINEAGE_GATES_V1` (series atom 3).
## Task Outcome Brief
- Owner decision (OD-A default): the non-fill terminal is named `CANCELLED`. If the owner chose another
  name before start, use it everywhere and record it; changing it mid-atom is
  `STOP LIFECYCLE_VOCABULARY_OWNER_DECISION_CHANGED`. `OPEN_RISK_STATES` semantics stay as in
  `risk_and_economics_v1.md` §8 (veto is a separate owner decision, A6).
- Named consumers: the future runner (reserve → attempt → fill), the owner's STOP/PAUSE/emergency-stop
  and close commands, Workbench/Trading Operations readouts, A5 (maps non-fill outcomes to `CANCELLED`).
- Cheapest falsifier (≤ 30 min): after 3.3 any stop variant still yields `OPEN`, or J4 stays `DRAINING`.
- Terminal outcomes: PASS; `STOP OPEN_RISK_STATES_SEMANTICS_CHANGE`; `STOP SECOND_POSITION_MODEL`;
  `STOP LIFECYCLE_VOCABULARY_OWNER_DECISION_CHANGED`; `STOP WRITE_SET_EXPANSION_REQUIRED`.
- User-visible result: "Close" on a pending intent cancels it; STOP finishes; retries of in-flight
  attempts say "reconcile first"; Trading Operations shows `INTENT_CANCELLED`.
- Evidence budget: focused tests; at most two exact-head CI iterations.
- Replan trigger: a consumer outside this write set enumerates lifecycle states and mis-renders `CANCELLED`.
## 1. Forensic truth (audit + independent reproduction)
- Resume branch of `accept_signal_decision` (existing position, `resume_only=True`) skips bot status,
  `entries_paused` and `new_entries_enabled`; a reserved (`skip_fill=True`) or `ATTEMPTING` intent reached
  `OPEN` under `STOP_BOT`, `PAUSE_NEW_ENTRIES` and `new_entries_enabled=false` (6/6 executor, 2/2 validator).
- `TRANSITIONS` has no exit from `WATCHED`/`SIGNALLED`/`INTENT_CREATED` except forward; `REQUEST_CLOSE_ALL`
  marks them `PREOPEN_NO_EXIT_INTENT`; `maybe_finish_drain` requires `RECONCILED` → `DRAINING` forever.
- Retry of `ATTEMPTING` → `fill_paper_from_signal` → `OPEN`; retry of `UNKNOWN` answers `opened=true`.
  TASK-26C already accepted `unknown_blocks_retry_and_new_action` and
  `retry_requires_bound_reconciliation`.
- `apply_paper_entry_fill` took `fee_bps=1` (strategy 10) and notional 150 (admitted 100) silently.
- State sets are duplicated: `paper_shadow_commands.TERMINAL_SETTLED`, `DRAIN_CLEARED`, unused
  `ACTIVE_INVENTORY`; `paper_shadow_operations.TERMINAL_SETTLED` (also imported by `risk_economics.py`).
## 2. Operational invariants
- E1 Stop dominance (INV-5), E2 no auto-fill in flight (INV-6), E3 drain liveness (INV-7), E4 admission
  binding (INV-8), E5 single-source state sets (INV-13) — as defined in the design §3.
- E6 `CANCELLED` is terminal, never in `OPEN_RISK_STATES`, never inventory, PnL `NOT_APPLICABLE`.
- E7 From `ATTEMPTING` only `REJECTED_BEFORE_SEND` or `DROPPED_OR_EXPIRED_NOT_PROCESSED` may cancel.
- E8 All new writes use A1 primitives (inside `immediate_write`, conditional transitions).
- E9 No test deletion, skip or weakening. Existing assertions change only where this contract changes the
  behavior (list them in the readout with the reason).
## 3. Execution
### 3.0 Hygiene and binding
Fresh worktree from `origin/main` that contains the A1 merge (`STOP A1_NOT_MERGED` otherwise); set
`expected_base` and `expected_upstream_oid` to that head; first commit adds this contract to `docs/tasks/`.
### 3.1 Baseline
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1 tests.test_paper_shadow_accounting_and_control_v1 tests.test_trading_runtime_policy_v1 tests.test_trading_operations_workbench_v2
```
### 3.2 Red: add `EntryIntentIntegrityTests` to the vertical module
Add imports:
```python
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection  # noqa: E402
from solana_alpha_lab.factory.paper_shadow_commands import maybe_finish_drain  # noqa: E402
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection  # noqa: E402
from solana_alpha_lab.factory.trading_operations import compose_trading_operations  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, show_policy  # noqa: E402
```
Helpers:
```python
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
```
Class:
```python
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
                    apply_operator_command(store, {"command_type": "PAUSE_NEW_ENTRIES", "idempotency_key": f"IDEM-{variant}", "bot_instance_id": bot})
                elif variant == "DISABLED":
                    apply_paper_policy(store, f"IDEM-{variant}", new_entries_enabled=False)
                elif variant == "INVALID":
                    apply_paper_policy(store, f"IDEM-{variant}")
                    store._conn.execute("UPDATE trading_runtime_policy_revisions SET policy_json = '{' WHERE mode = 'PAPER'")
                else:
                    store.set_bot_status(bot, "DRAINING")
                with self.assertRaisesRegex(PaperPlaneError, code):
                    accept(store, self.strategy, sid)
                row = store.get_position(reserved["position_id"])
                self.assertEqual((row["state"], row["cancel_reason_code"]), ("CANCELLED", reason))
                self.assertNotIn("PAPER_SIMULATION_OBSERVED", event_types(store, position_id=row["position_id"]))

    def test_stop_bot_cancels_pre_attempt_intents_and_reaches_stopped(self) -> None:
        store = self.store()
        reserved = self.reserve(store, "SIGDEC-VERT-J4")
        stop = apply_operator_command(store, {"command_type": "STOP_BOT", "idempotency_key": "IDEM-VERT-J4", "bot_instance_id": reserved["bot_instance_id"]})
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
        result = apply_operator_command(store, {"command_type": "REQUEST_CLOSE_ALL", "idempotency_key": "IDEM-VERT-CA", "bot_instance_id": bot, "expected_open_position_set_sha256": sha})
        fanout = {item["position_id"]: item for item in result["fanout"]}
        self.assertEqual(fanout[pending["position_id"]]["state"], "CANCELLED")
        self.assertEqual(fanout[flying["position_id"]].get("skipped"), "ATTEMPT_IN_FLIGHT_RECONCILE_REQUIRED")
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
            accept(store, self.strategy, "SIGDEC-VERT-STALE", as_of="2026-09-03T12:25:01Z")  # max_age 900 s
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
        lifecycle = build_lifecycle_projection(ROOT, paper_plane_store=store, research_store=_NoResearch(), projected_at=T0, git_sha="0" * 40)
        self.assertIn("CANCELLED", {e.get("native_state") for e in lifecycle["entities"]})
```
Adapt only key names if a projection names a field differently (`traces`, `position_rows`, `entities`) —
never the asserted meaning. Expected red: every test except the slot test's first `assertRaises`.
### 3.3 Fix: `paper_plane.py`
1. Vocabulary and single-source sets (below `TRANSITIONS`; append `"CANCELLED"` to `POSITION_STATES`):
```python
TRANSITIONS: dict[str, set[str]] = {
    "WATCHED": {"SIGNALLED", "CANCELLED"},
    "SIGNALLED": {"INTENT_CREATED", "CANCELLED"},
    "INTENT_CREATED": {"ATTEMPTING", "CANCELLED"},
    "ATTEMPTING": {"OPEN", "PARTIAL", "UNKNOWN", "UNRESOLVED", "CANCELLED"},
    "OPEN": {"EXIT_REQUIRED", "EXITING"},
    "PARTIAL": {"EXIT_REQUIRED", "EXITING"},
    "UNKNOWN": {"EXIT_REQUIRED", "EXITING", "UNRESOLVED", "RECONCILED"},
    "EXIT_REQUIRED": {"EXITING"},
    "EXITING": {"CLOSED", "UNRESOLVED"},
    "CLOSED": {"RECONCILED"},
    "UNRESOLVED": {"RECONCILED"},
    "RECONCILED": set(),
    "CANCELLED": set(),
}
PRE_ATTEMPT_STATES = frozenset({"WATCHED", "SIGNALLED", "INTENT_CREATED"})
IN_FLIGHT_STATES = frozenset({"ATTEMPTING", "UNKNOWN"})
OPERATOR_SETTLED_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})
DRAIN_CLEARED_STATES = frozenset({"RECONCILED", "CANCELLED"})
CLOSING_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})
DEFINITIVE_NON_FILL_REASONS = frozenset({"REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED"})
CANCEL_REASONS = frozenset(
    {
        "OPERATOR_CANCEL",
        "OPERATOR_CLOSE_ALL",
        "OPERATOR_STOP",
        "ENTRIES_PAUSED",
        "NEW_ENTRIES_DISABLED",
        "RUNTIME_POLICY_INVALID",
        "BOT_DRAINING",
        "BOT_STOPPED",
        "SIGNAL_EXPIRED",
    }
) | DEFINITIVE_NON_FILL_REASONS
```
   Export the new names in `__all__`. `OPEN_RISK_STATES` is unchanged.
2. Migration `_migrate_entry_intent_integrity_v1()` called from `__init__` after the existing
   migrations: `_ensure_column(self._conn, "positions", "cancel_reason_code", "TEXT")` and
   `_ensure_column(self._conn, "positions", "admitted_fee_bps", "INTEGER")`.
3. `cancel_entry_intent`:
```python
    def cancel_entry_intent(self, position_id: str, *, reason_code: str) -> dict[str, Any]:
        if reason_code not in CANCEL_REASONS:
            raise PaperPlaneError("CANCEL_REASON_INVALID")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            state = str(position["state"])
            if state == "CANCELLED":
                return position
            if state == "ATTEMPTING" and reason_code not in DEFINITIVE_NON_FILL_REASONS:
                raise PaperPlaneError("CANCEL_REQUIRES_DEFINITIVE_NON_FILL:ATTEMPTING")
            if state not in PRE_ATTEMPT_STATES and state != "ATTEMPTING":
                raise PaperPlaneError(f"CANCEL_STATE_INVALID:{state}")
            if position.get("entry_price_dec") not in {None, ""}:
                raise PaperPlaneError("CANCEL_AFTER_FILL_FORBIDDEN")
            self.transition(position_id, "CANCELLED")
            self._conn.execute(
                "UPDATE positions SET cancel_reason_code = ? WHERE position_id = ?",
                (reason_code, position_id),
            )
            self.append_execution_event(
                event_type="ENTRY_INTENT_CANCELLED",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={**_identity_fields(position), "from_state": state, "cancel_reason_code": reason_code},
            )
            updated = self.get_position(position_id)
        assert updated is not None
        return updated
```
4. `freeze_admission_binding(..., admitted_fee_bps: int | None = None)`: add
   `admitted_fee_bps = COALESCE(admitted_fee_bps, ?)`. In `accept_signal_decision` pass
   `admitted_fee_bps=int(strategy["notional_policy"]["fee_bps"])`.
5. `apply_paper_entry_fill(..., fee_bps: int | None = None, ...)`: inside the A1 transaction, after the
   state checks and the price/notional validity check and before any transition or UPDATE:
```python
            fee_bps = _bound_entry_fee_bps(position, fee_bps)
            admitted = position.get("admitted_entry_notional_usd_dec")
            if admitted not in {None, ""} and notional > Decimal(str(admitted)):
                raise PaperPlaneError("ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION")
```
   Move the `ATTEMPTING → OPEN` transition after these checks. Module helper:
```python
def _bound_entry_fee_bps(position: Mapping[str, Any], requested: int | None) -> int:
    admitted = position.get("admitted_fee_bps")
    if admitted is not None:
        if requested is not None and int(requested) != int(admitted):
            raise PaperPlaneError("ENTRY_FILL_FEE_MISMATCH")
        return int(admitted)
    if requested is None:
        raise PaperPlaneError("ENTRY_FILL_FEE_REQUIRED")
    return int(requested)
```
6. `accept_signal_decision`, replace the block from `as_of_dt = ...` to `bot_instance_id =
   bot["bot_instance_id"]` (the mismatch checks and the new-admission body stay verbatim where marked):
```python
    as_of_dt = _parse_utc(as_of) if as_of else _parse_utc(decision["decision_at"])
    decision_at = _parse_utc(decision["decision_at"])
    max_age = int(strategy["signal_input"]["max_age_seconds"])
    stale = (as_of_dt - decision_at).total_seconds() > max_age
    position_id = position_id_for_signal_decision(str(decision["signal_decision_id"]))
    if stale and store.get_position(position_id) is None:
        raise PaperPlaneError("SIGNAL_DECISION_STALE")
    admitted_notional = Decimal(str(strategy["notional_policy"]["notional_usd"]))
    was_existing = False
    resume_only = False
    block_code: str | None = None
    bot_instance_id = ""
    with store.immediate_write():
        existing = store.get_position(position_id)
        if existing is not None:
            ...  # unchanged: SIGNAL_ACTIVATION_EPOCH_MISMATCH / SIGNAL_POSITION_STRATEGY_MISMATCH /
                 # SIGNAL_BOT_INSTANCE_MISMATCH checks
        bot = store.start_bot(strategy, mode=mode, activation_epoch_id=str(decision["activation_epoch_id"]))
        if existing is not None:
            was_existing = True
            state = str(existing["state"])
            base = {
                "action": action,
                "reason_code": decision["reason_code"],
                "signal_decision_id": decision["signal_decision_id"],
                "position_id": position_id,
                "idempotent": True,
                "state": state,
                "bot_instance_id": bot["bot_instance_id"],
                "activation_epoch_id": decision["activation_epoch_id"],
            }
            if state == "OPEN":
                return {**base, "opened": True}
            if state in IN_FLIGHT_STATES:
                return {**base, "opened": False, "reconciliation_required": True}
            if state not in PRE_ATTEMPT_STATES:
                return {**base, "opened": state == "PARTIAL"}
            block_code, cancel_reason = _resume_block(store, bot, mode, stale=stale)
            if block_code is not None:
                store.cancel_entry_intent(position_id, reason_code=str(cancel_reason))
            else:
                ...  # unchanged: frozen admission / ADMISSION_BINDING_MISSING
                resume_only = True
        if block_code is None and not resume_only:
            ...  # unchanged new-admission body (status and pause checks, evaluate_admission,
                 # PRE_TRADE_RISK_SNAPSHOT, open_position_from_signal, freeze_admission_binding with
                 # admitted_fee_bps, SIGNAL_DECISION_ACCEPTED)
        bot_instance_id = bot["bot_instance_id"]
    if block_code:
        raise PaperPlaneError(block_code)
```
   Module helper:
```python
def _resume_block(
    store: PaperPlaneStore, bot: Mapping[str, Any], mode: str, *, stale: bool
) -> tuple[str | None, str | None]:
    """Stop dominance for an admitted, unattempted intent (design §6.1 order)."""

    if stale:
        return "SIGNAL_DECISION_STALE", "SIGNAL_EXPIRED"
    status = str(bot.get("status") or "")
    if status in {"DRAINING", "STOPPED"}:
        return f"BOT_STATUS_BLOCKS_ENTRY:{status}", f"BOT_{status}"
    if int(bot.get("entries_paused") or 0) == 1:
        return "ENTRIES_PAUSED", "ENTRIES_PAUSED"
    from solana_alpha_lab.factory.trading_runtime_policy import (
        STATUS_INVALID,
        STATUS_VALID,
        resolve_current_policy,
    )

    current = resolve_current_policy(store, mode)
    if current["status"] == STATUS_INVALID:
        return "RUNTIME_POLICY_INVALID", "RUNTIME_POLICY_INVALID"
    policy = current.get("policy")
    if current["status"] == STATUS_VALID and policy is not None and not policy.get("new_entries_enabled"):
        return "BLOCK_NEW_ENTRIES_DISABLED", "NEW_ENTRIES_DISABLED"
    return None, None
```
### 3.4 Fix: consumers
- `paper_shadow_commands.py`: import `PRE_ATTEMPT_STATES`, `OPERATOR_SETTLED_STATES`,
  `DRAIN_CLEARED_STATES` from `paper_plane`; delete the local `ACTIVE_INVENTORY` (unused),
  `TERMINAL_SETTLED` and `DRAIN_CLEARED`; `_inventory_position_ids` uses `OPERATOR_SETTLED_STATES`,
  `_drain_remaining_ids` uses `DRAIN_CLEARED_STATES`.
  - `REQUEST_CLOSE_POSITION`: `CLOSEABLE` path unchanged; `EXIT_REQUIRED` and `CANCELLED` → applied,
    state unchanged; `PRE_ATTEMPT_STATES` → `store.cancel_entry_intent(position_id,
    reason_code="OPERATOR_CANCEL")`, append `OPERATOR_COMMAND_APPLIED` (`from_state`), result state
    `CANCELLED`; anything else → `CLOSE_POSITION_STATE_INVALID:<state>`.
  - `REQUEST_CLOSE_ALL` fan-out: `PRE_ATTEMPT_STATES` → cancel with `OPERATOR_CLOSE_ALL`,
    `{"position_id", "state": "CANCELLED"}` (counts as a side effect); `ATTEMPTING` →
    `{"position_id", "state", "skipped": "ATTEMPT_IN_FLIGHT_RECONCILE_REQUIRED"}`; the rest unchanged.
  - `STOP_BOT`: before computing inventory, cancel every pre-attempt position of the bot with
    `OPERATOR_STOP`; add `"cancelled_intents": [<sorted ids>]` to the result and the event payload.
- `paper_shadow_operations.py`: `from ...paper_plane import OPEN_RISK_STATES, OPERATOR_SETTLED_STATES,
  PaperPlaneStore`; `TERMINAL_SETTLED = OPERATOR_SETTLED_STATES  # public alias used by risk_economics`;
  `position_pnl_view` first branch: `if state == "CANCELLED": return {"net_pnl_usd": None,
  "pnl_status": "NOT_APPLICABLE", "pnl_evidence_class": None}`; projection field
  `"cancelled_intents": sum(1 for p in positions if str(p["state"]) == "CANCELLED")`.
- `trading_operations.py`: `EVENT_STAGE["ENTRY_INTENT_CANCELLED"] = "EXECUTION_INTENT"`; in the trace loop
  after the `RECONCILIATION`/`UNRESOLVED` rule: `if event_type == "ENTRY_INTENT_CANCELLED":
  bucket["blocker"] = bucket.get("blocker") or "INTENT_CANCELLED"`; update `COMMAND_SPECS` texts for
  `REQUEST_CLOSE_POSITION` (pre-attempt → `CANCELLED`), `REQUEST_CLOSE_ALL` (pre-attempt cancelled,
  `ATTEMPTING` skipped: reconcile first) and `STOP_BOT` (cancels pre-attempt intents; `STOPPED` when
  drain-cleared = `RECONCILED|CANCELLED`).
- Workbench and lifecycle projection: no code change expected (`CANCELLED` renders as history; state is
  passed through). If a consumer outside this write set mis-renders it → replan trigger.
### 3.5 Contracts (durable truth)
- `docs/contracts/trading_runtime_policy_v1.md` §6: resume of an admitted pre-attempt intent re-checks
  stale, bot status, pause, policy validity and `new_entries_enabled`; a match cancels the intent with a
  reason and raises the code; `ATTEMPTING`/`UNKNOWN` never auto-fill (`reconciliation_required`). §7:
  `new_entries_enabled=false` also stops admitted, unattempted intents. Admission freezes
  `admitted_fee_bps`.
- `docs/contracts/risk_and_economics_v1.md` §8: `CANCELLED` is terminal, not entry-admission risk, PnL
  `NOT_APPLICABLE`.
- `docs/contracts/trading_operations_workbench_v2.md`: new command semantics and `INTENT_CANCELLED`.
- Design file: add "A2 delivered in this PR" to §11.
### 3.6 Focused green, suite, propagation
```text
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_execution_integrity_vertical_v1
uv run --locked --managed-python python -B -m unittest tests.test_paper_shadow_accounting_and_control_v1 tests.test_trading_runtime_admission_concurrency_v1 tests.test_factory_strategy_execution_boundary_v1 tests.test_trading_runtime_policy_v1 tests.test_trading_runtime_policy_backup_restore_v1 tests.test_trading_operations_workbench_v2 tests.test_owner_trading_operability_workbench_v1 tests.test_owner_operations_cockpit_v1 tests.test_factory_v1_owner_cockpit tests.test_risk_and_economics_v1 tests.test_owner_lifecycle_projection_spine_v1 tests.test_early_state_to_paper_vertical_slice tests.test_factory_unattended_shadow_vertical_slice tests.test_execution_domain_modularity_and_fast_ci_v1 tests.test_science_to_strategy_handoff_v1
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <expected_base>
```
Register this contract and the evidence trio in `catalog/assets/core.yaml` (mirror A1's entries).
### 3.7 Review and finish
Critics attack: (1) any path that still turns a pre-attempt intent into `OPEN` while stopped (search every
caller of `fill_paper_from_signal` and `transition(..., "OPEN")`); (2) any consumer enumerating states
that now mis-counts `CANCELLED` (grep `"RECONCILED"` and `"CLOSED"` literals in `src/`); (3) `CANCELLED`
leaking into `OPEN_RISK_STATES`, exposure, loss streak, drawdown or PnL aggregates; (4) the owner-UX
critic: command texts and readout say what happens to pending intents in plain words; (5) what passes
every test yet breaks research validity: paper economics no longer comparable with pre-A2 results for
stopped bots — state it in the readout (only stopped-bot retries change). Then Factory Fit, readout in
Russian, evidence, bind, preflight-push, PR.
## 4. Vertical Capability Repair Loop
```text
bind (A1 merged) + baseline
-> red EntryIntentIntegrityTests (stop matrix, J4, close-all, close-one, in-flight retry, cancel rules,
   slot release, stale resume, fill binding, consumers)
-> vocabulary + cancel + resume dominance + binding (3.3)
-> consumers (3.4) -> contracts (3.5)
-> focused green + execution-domain suite (3.6)
   |- a legacy assertion contradicts the new contract -> change it with the reason in the readout
   '- a consumer outside the write set breaks -> STOP WRITE_SET_EXPANSION_REQUIRED
-> isolated review (incl. OWNER_UX) -> finish -> bind -> preflight-push -> ONE PR -> exact-head CI
-> merge-readiness -> owner phrase -> guarded merge -> post-merge readback
```
## 5. Definition of Done
1. `EntryIntentIntegrityTests` and `WriteIntegrityTests` green; stop matrix 0/4 `OPEN`; J4 reaches
   `STOPPED`; in-flight retries answer `reconciliation_required` without state or event change.
2. `CANCELLED` excluded from open sets, exposure and PnL aggregates; `pnl_status=NOT_APPLICABLE`.
3. Fee and notional overrides rejected with the exact codes; honest fills unchanged (accounting fixtures).
4. One definition per state set in `paper_plane.py`; no local lifecycle sets left in commands/operations.
5. Execution-domain suite green; changed legacy assertions listed with reasons; zero weakened tests.
6. Contracts updated; exact-head CI green.
## 6. Non-goals
Decision gates and lineage (A3); readonly freshness (A4); attempts and observation mapping (A5); veto of
entries on unresolved inventory (A6); Workbench HTML changes; exit-side cancel semantics.
## 7. Rollback and limitations
Rollback: revert the merge commit; `CANCELLED` rows would then be unknown to old code and render as
unknown states — acceptable for paper data (document in the readout). Limitation: `PARTIAL` keeps its
legacy meaning (swaps do not produce partial fills).
## 8. Final return
```yaml
capability: PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1
base: <40hex>
head: <40hex>
terminal_state_name: CANCELLED
stop_matrix_open: {before: 6/6, after: 0/4}
j4_stopped_without_fill: true
in_flight_retry: {attempting: reconciliation_required, unknown: reconciliation_required}
fill_binding: {fee_override: ENTRY_FILL_FEE_MISMATCH, notional_over: ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION}
legacy_assertions_changed: [<test::name: reason>]
execution_domain_modules: {passed: <n>, failed: 0}
tests_weakened: 0
ci: {exact_head_run: <id>, result: success}
pr: <url>
```
