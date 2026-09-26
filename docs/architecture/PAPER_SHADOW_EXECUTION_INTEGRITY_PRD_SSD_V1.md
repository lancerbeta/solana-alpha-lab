# PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1

Status: `DESIGN_READY_FOR_ATOMS` — series of 5 atoms plus 1 owner-gated option. No live authority.

Authoring base: `origin/main` `ae678372f2a96fbc20c519c23905ae5c44332458` (2026-09-26). Every file of the
execution domain is byte-identical to the audited anchor `94a4ea74afb6c921f4972312840be2de5eeba4f9`.

Source: vertical capability audit of "accepted hypothesis → closed position" (plan rev 2 → executor
evidence → independent validation with 2/2 reproductions). Verdict `MATERIAL_REPAIR_FOUND`, audit
validity `VALID_WITH_LIMITATIONS`. This file is the durable design. Every atom has its own exact task
contract in `docs/tasks/`; a contract wins over this file on write set, stop conditions and DoD.

## 0. Entry / outcome

- `DECISION_DELTA`: the PAPER/SHADOW plane stays truthful under concurrent writers, crashes, operator
  stops and non-fill outcomes, and gains the provider-neutral execution-attempt seam that a future real
  executor plugs into. No second position model, no new store, no dependency, no provider call, no live
  authority.
- Named consumers: (1) the future v1.1 runner of the first promoted hypothesis; (2) the owner through
  Workbench (operator commands, Trading Operations traces, Risk & Economics); (3) a SHADOW runner with
  real quotes — first user of the attempt seam; (4) promotion decisions that read PAPER/SHADOW results.
- Series terminal: `PAPER_SHADOW_EXECUTION_INTEGRITY_SERIES_PASS` = A1–A5 merged with their DoD. A6 only
  after owner decision OD-1.
- Why now: no production code calls the v1.1 engine yet (only tests and
  `scripts/factory_paper_shadow_operator_smoke.py`). Once a runner is built on the current API, the API
  shape and the lifecycle vocabulary become expensive to change.

## 1. Product requirement (frozen)

### 1.1 Confirmed problems

| ID | Finding (evidence) | Kind | Atom |
| --- | --- | --- | --- |
| F1 | Retry of a reserved or in-flight entry reaches `OPEN` under `STOP_BOT`, `PAUSE_NEW_ENTRIES`, `new_entries_enabled=false` (6/6 + 2/2) | DEFECT | A2 |
| F2 | Pre-attempt intents have no non-fill terminal; close-all skips them; `STOPPED` is unreachable without a fabricated fill | DEFECT | A2 |
| F3 | Retry of `ATTEMPTING` auto-fills to `OPEN`; retry of `UNKNOWN` answers `opened=true` | DEFECT (latent) | A2 |
| F4 | Entry fill accepts `fee_bps` ≠ strategy and notional > admitted, silently | DEFECT | A2 |
| F5 | Lost update: operator close overwrites a concurrent `RECONCILED` (55/200 natural, 2/2 hook) | DEFECT | A1 |
| F6 | Crash between a state write and its event leaves a permanent lineage gap | DEFECT | A1 |
| F7 | `execution_events()` is not in causal order inside one second | observability | A1 |
| F8 | Missing `as_of` makes staleness vacuous; future-dated decision accepted; same id with another body answers idempotent | DEFECT (latent) | A3 |
| F9 | No strategy spec hash, decision fingerprint or evidence refs in SQLite; exit overwrites entry `reason_code`; ExitDecision acceptance writes no event; V2 ExitDecision closes a V1 position | SEAM_GAP | A3 |
| F10 | Readonly store (`immutable=1`) does not see committed WAL of a live writer (2/2, stress 910/910 stale) | DEFECT (latent) | A4 |
| F11 | External executor outcomes cannot be represented (PARTIAL, NO_ROUTE, REJECTED, TIMEOUT; no attempt identity; external ref → trace GAP) | SEAM_GAP | A5 |
| F12 | Two disconnected execution models: canonical `execution_attempts` / `strategy_outcomes` (`schemas/schema_v1.sql`, `docs/contracts/data_contract_v1.md`, TASK-26C) vs PaperPlane | duplicated mechanism | A5 |
| G1 | `UNRESOLVED` / `EXIT_*` inventory frees the entry slot (`risk_and_economics_v1.md` §8) while ARCH-INTENT-002 and TASK-26C require a veto | GOAL_ALIGNMENT | OD-1 → A6 |

What holds and must not regress: `REAL_FILL`, `micro_live` and `LIVE` stay blocked; a handoff-rendered
StrategyVersion executes unmodified; Decimal PnL equals an independent oracle to the cent, including
micro-prices; `max_open_positions` and `max_age_seconds` hold when `as_of` is passed; exits work under
every entry-side stop through the operator path; risk inventory is flagged in every owner consumer;
the activation decision lives in `resolve_activation_epoch`; two epochs stay separate.

### 1.2 Goals

1. Atomic, conditional writes: a state change and its lineage event commit together or not at all.
2. Honest entry lifecycle: every intent either fills through an admitted, non-stopped path or ends in
   an honest non-fill terminal; a possibly-submitted attempt is never auto-filled.
3. Decision identity: a decision is evaluated against an explicit clock and is bound to its exact body.
4. Fresh owner view while a writer is running, with GET purity preserved.
5. A provider-neutral attempt seam aligned with the canonical `execution_attempts` vocabulary.

### 1.3 Non-goals

LIVE, micro-live, wallet, signer, transactions, providers, quote capture, the runner itself, an
activation registry, Workbench HTML redesign, VPS actions, legacy v1.0 behavior changes (except the
spec-drift guard in A3), writing canonical DuckDB rows, partial-quantity machinery for swaps
(Solana swaps are atomic; realized vs requested amounts cover slippage).

### 1.4 Owner decisions and defaults

Defaults apply unless the owner overrides them before the atom that consumes them starts.

| ID | Decision | Default | Consumed by |
| --- | --- | --- | --- |
| OD-A | Name of the non-fill terminal state | `CANCELLED` | A2 |
| OD-1 | Should unresolved or exit-pending inventory veto new entries | Keep §8 (`OFF`); offer an opt-in policy knob via A6 | A6 |
| OD-2 | Depth of convergence with the canonical execution model | Vocabulary and identity alignment only; no cross-store writes | A5 |
| OD-3 | Is a scientific ExitDecision valid after its epoch is deactivated | Out of series; decided with the activation atom | — |

## 2. Current truth (authoring base)

Engine: `src/solana_alpha_lab/factory/paper_plane.py` (`PaperPlaneStore`, `accept_signal_decision`,
`accept_exit_decision`, fills), `strategy_runtime.py`, `trading_runtime_policy.py`,
`paper_shadow_commands.py`, projections `paper_shadow_operations.py`, `risk_economics.py`,
`trading_operations.py`, `lifecycle_projection.py` (pass-through `native_state`), adapter
`application.py` (operator commands; readonly store per GET). Domain boundary: `configs/execution_domain_v1.json`.

Writable connections use `isolation_level=None` (autocommit) and `busy_timeout=5000`; only
`immediate_write()` opens `BEGIN IMMEDIATE` (thread-local depth, nesting is a no-op). Readonly
connections use `mode=ro&immutable=1`.

State-set definitions currently disagree: `OPEN_RISK_STATES` (7 states, admission), local
`TERMINAL_SETTLED` in both `paper_shadow_commands.py` and `paper_shadow_operations.py`,
`DRAIN_CLEARED` (only `RECONCILED`), an unused `ACTIVE_INVENTORY`, and a third definition inside
legacy `run_shadow_tick`. `risk_economics.py` imports `TERMINAL_SETTLED` from `paper_shadow_operations.py`.

## 3. Target invariants

- INV-1 Atomic transition: `transition()` re-reads the state inside `BEGIN IMMEDIATE` and writes with
  `WHERE state = <read>`; rowcount ≠ 1 → `STALE_STATE`.
- INV-2 Atomic lineage: every event that describes a state change is appended in the same transaction.
- INV-3 Atomic commands: idempotency lookup, side effects and command record are one transaction.
- INV-4 Causal order: `execution_events()` returns insertion (`rowid`) order.
- INV-5 Stop dominance: after `STOP_BOT`, `PAUSE_NEW_ENTRIES`, `new_entries_enabled=false` or an invalid
  policy, no pre-attempt intent reaches `OPEN`; it becomes `CANCELLED` with a reason.
- INV-6 No auto-fill in flight: `ATTEMPTING` and `UNKNOWN` never transition to `OPEN` on a signal retry;
  the answer is `reconciliation_required=true`, `opened=false`.
- INV-7 Drain liveness: `STOP_BOT` reaches `STOPPED` without a fill claim when only pre-attempt intents remain.
- INV-8 Admission binding: realized entry notional ≤ admitted notional; modeled fee is frozen at admission.
- INV-9 Decision identity: every decision needs an explicit `as_of`; future beyond skew is rejected; one
  `signal_decision_id` binds one body (fingerprint).
- INV-10 Lineage completeness: a position can be traced by stored columns and events to the strategy
  spec hash, activation epoch, decision fingerprint and evidence refs, admission snapshot, entry and exit
  reasons, and (A5) execution attempts.
- INV-11 Fresh readonly view: a readonly store sees every committed transaction; steady-state GET creates
  no file.
- INV-12 Honest outcomes (A5): each canonical terminal state maps to exactly one truthful lifecycle move
  through public API.
- INV-13 Single source of state sets: lifecycle state sets are defined once in `paper_plane.py` and imported.

## 4. Lifecycle vocabulary v1.1

### 4.1 States

| State | Meaning | Inventory | Entry risk (`OPEN_RISK_STATES`) | Operator-settled | Drain-cleared |
| --- | --- | --- | --- | --- | --- |
| WATCHED | admitted reservation, no attempt | none | yes | no | no |
| SIGNALLED | reservation progressing | none | yes | no | no |
| INTENT_CREATED | intent persisted before any send | none | yes | no | no |
| ATTEMPTING | attempt possibly submitted | unknown | yes | no | no |
| OPEN | entry filled | yes | yes | no | no |
| PARTIAL | legacy vocabulary; not produced for swaps | yes | yes | no | no |
| UNKNOWN | entry outcome unknown | unknown | yes | no | no |
| EXIT_REQUIRED | exit requested | yes | no (§8) | no | no |
| EXITING | exit possibly submitted | yes/unknown | no (§8) | no | no |
| CLOSED | exit filled, awaiting reconcile | none | no | yes | no |
| UNRESOLVED | exit outcome unknown | unknown | no (§8) | no | no |
| RECONCILED | closure verified | none | no | yes | yes |
| CANCELLED (A2, OD-A) | intent ended without any fill | none ever | no | yes | yes |

### 4.2 Transitions

```text
WATCHED        -> SIGNALLED | CANCELLED(A2)
SIGNALLED      -> INTENT_CREATED | CANCELLED(A2)
INTENT_CREATED -> ATTEMPTING | CANCELLED(A2)
ATTEMPTING     -> OPEN | PARTIAL | UNKNOWN | UNRESOLVED | CANCELLED(A2, definitive non-fill only)
OPEN           -> EXIT_REQUIRED | EXITING
PARTIAL        -> EXIT_REQUIRED | EXITING
UNKNOWN        -> EXIT_REQUIRED | EXITING | UNRESOLVED | RECONCILED | OPEN(A5) | CANCELLED(A5)
EXIT_REQUIRED  -> EXITING
EXITING        -> CLOSED | UNRESOLVED | EXIT_REQUIRED(A5)
CLOSED         -> RECONCILED
UNRESOLVED     -> RECONCILED | EXIT_REQUIRED(A5)
RECONCILED     -> (terminal)
CANCELLED      -> (terminal)
```

### 4.3 Single-source state sets (A2, in `paper_plane.py`)

```python
PRE_ATTEMPT_STATES = frozenset({"WATCHED", "SIGNALLED", "INTENT_CREATED"})
IN_FLIGHT_STATES = frozenset({"ATTEMPTING", "UNKNOWN"})
OPERATOR_SETTLED_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})
DRAIN_CLEARED_STATES = frozenset({"RECONCILED", "CANCELLED"})
CLOSING_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})  # set closed_at
```

`OPEN_RISK_STATES` keeps its current value. `paper_shadow_operations.TERMINAL_SETTLED` becomes an alias
of `OPERATOR_SETTLED_STATES` (kept for `risk_economics.py`).

### 4.4 Mapping to intent and canonical vocabulary

ARCH-INTENT-005 §7 defines the conceptual lifecycle; `CANCELLED` refines "intent not attempted" and is
not a second model. Canonical mapping: a `CANCELLED` position has canonical inventory `FLAT` and, when
an attempt exists (A5), a terminal attempt `REJECTED_BEFORE_SEND`, `DROPPED_OR_EXPIRED_NOT_PROCESSED` or
`LANDED_FAILED`. `UNKNOWN` / `UNRESOLVED` correspond to `UNKNOWN_REQUIRES_RECONCILIATION` and
`UNRESOLVED_REQUIRES_RECOVERY`.

## 5. Write integrity model (A1)

| API | Transaction boundary after A1 |
| --- | --- |
| `transition()` | own `BEGIN IMMEDIATE` unless nested; conditional UPDATE |
| `accept_signal_decision()` | admission txn (unchanged) + one txn for fill and `EXECUTION_INTENT_CREATED` / `POSITION_TRANSITION`; events only if this call moved the position to `OPEN` |
| `apply_paper_entry_fill()` | one txn: read, transition, economics, `PAPER_SIMULATION_OBSERVED` / `SHADOW_EXECUTABLE_OBSERVED` |
| `apply_paper_exit_fill()` | one txn: read (no stale `state0`), transitions, economics, `*_EXIT_*` and `RECONCILIATION` |
| `apply_exit_decision()` | one txn |
| `record_position_mark()` | one txn |
| `set_entries_paused()`, `set_bot_status()` | one txn each (nested inside commands) |
| `apply_operator_command()` | one txn: idempotency lookup, effects, events, record |
| `maybe_finish_drain()` | one txn |
| `execution_events()` | `ORDER BY rowid` |

Legacy v1.0 paths keep working: their `transition()` calls become individually atomic.

## 6. Entry intent model (A2)

### 6.1 Retry of an existing position in `accept_signal_decision`

| Existing state | Result |
| --- | --- |
| OPEN | idempotent, `opened=true` (unchanged) |
| ATTEMPTING, UNKNOWN | idempotent, `opened=false`, `reconciliation_required=true`, no state change |
| PARTIAL, EXIT_REQUIRED, EXITING, CLOSED, RECONCILED, UNRESOLVED, CANCELLED | idempotent, `opened = state == "PARTIAL"` |
| WATCHED, SIGNALLED, INTENT_CREATED | evaluate stops in order: stale → bot `DRAINING`/`STOPPED` → `entries_paused` → policy `INVALID` → policy `new_entries_enabled=false`. First match: `cancel_entry_intent(reason)` then raise the matching code. No match: resume with the frozen admission (unchanged) |

Reason codes: `SIGNAL_EXPIRED`, `BOT_DRAINING`, `BOT_STOPPED`, `ENTRIES_PAUSED`, `RUNTIME_POLICY_INVALID`,
`NEW_ENTRIES_DISABLED`, `OPERATOR_CANCEL`, `OPERATOR_CLOSE_ALL`, `OPERATOR_STOP`, `REJECTED_BEFORE_SEND`,
`DROPPED_OR_EXPIRED_NOT_PROCESSED` (+ `LANDED_FAILED` in A5). From `ATTEMPTING` only the definitive
non-fill reasons are accepted.

### 6.2 Operator commands

- `REQUEST_CLOSE_POSITION`: pre-attempt → `CANCELLED` (`OPERATOR_CANCEL`); `CANCELLED` idempotent;
  `ATTEMPTING` → `CLOSE_POSITION_STATE_INVALID:ATTEMPTING` (reconcile first); other rules unchanged.
- `REQUEST_CLOSE_ALL`: pre-attempt → `CANCELLED` (`OPERATOR_CLOSE_ALL`); `ATTEMPTING` →
  `skipped: ATTEMPT_IN_FLIGHT_RECONCILE_REQUIRED`; snapshot excludes `OPERATOR_SETTLED_STATES`.
- `STOP_BOT`: cancels the bot's pre-attempt intents (`OPERATOR_STOP`), then `DRAINING` or `STOPPED` by
  `DRAIN_CLEARED_STATES`; result lists `cancelled_intents`.

### 6.3 Fill binding

`freeze_admission_binding` also freezes `admitted_fee_bps` (strategy `notional_policy.fee_bps`).
`apply_paper_entry_fill(fee_bps=None)` uses it; a different explicit value → `ENTRY_FILL_FEE_MISMATCH`;
notional > admitted → `ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION`; positions without an admission binding
(legacy) keep the caller fee and require it (`ENTRY_FILL_FEE_REQUIRED`).

### 6.4 Projections

`position_pnl_view`: `CANCELLED` → `pnl_status=NOT_APPLICABLE`, `net_pnl_usd=None`. Operations projection
adds `cancelled_intents`. Trading Operations maps `ENTRY_INTENT_CANCELLED` to stage `EXECUTION_INTENT` and
sets trace blocker `INTENT_CANCELLED`. Workbench needs no change (`CANCELLED` is not in
`ACTIVE_STATE_PRIORITY`, so it renders as history). Lifecycle projection passes the state through.

## 7. Decision identity and lineage (A3)

- `accept_signal_decision`: `as_of` required (`SIGNAL_AS_OF_REQUIRED`); `decision_at - as_of >
  SIGNAL_MAX_CLOCK_SKEW_SECONDS (2)` → `SIGNAL_DECISION_FROM_FUTURE`.
- Fingerprint: `signal_decision_sha256 = strategy_runtime.canonical_spec_sha256(validated decision)`;
  stored on the position; a different body under the same id → `SIGNAL_DECISION_IDEMPOTENCY_MISMATCH`
  (for ENTER retries and for any decision whose id already owns a position). Legacy rows with NULL
  fingerprint are not checked.
- Columns: `positions.signal_decision_sha256`, `positions.strategy_spec_sha256`,
  `positions.exit_reason_code`, `bot_instances.strategy_spec_sha256`.
- `start_bot`: stored spec hash ≠ loaded spec hash → `STRATEGY_SPEC_DRIFT`; NULL is backfilled once.
- `SIGNAL_DECISION_ACCEPTED` payload adds `signal_decision_sha256`, `evidence_refs`,
  `source_hypothesis_refs`, `first_reliable_available_at`, `strategy_spec_sha256`.
- `accept_exit_decision`: decision `strategy_version` ≠ position `strategy_version_label` →
  `EXIT_POSITION_VERSION_MISMATCH`. `apply_exit_decision` writes `exit_reason_code` (entry `reason_code`
  preserved) and appends `EXIT_DECISION_ACCEPTED` (stage `POSITION`).

## 8. Readonly freshness (A4)

`_connect_sqlite(readonly=True)`: if `<db>-wal` exists → `mode=ro` (WAL-aware, sees committed frames);
otherwise → `mode=ro&immutable=1` (no WAL means the main file is complete; creates no file). A failure to
open WAL-aware falls back to immutable. `PaperPlaneStore.read_mode` ∈ `WAL_AWARE`, `IMMUTABLE_SNAPSHOT`,
`IMMUTABLE_FALLBACK`. Same helper is a candidate for `OperationalStore` later (non-goal here).

## 9. Execution attempt seam (A5)

### 9.1 Ledger (PaperPlaneStore, additive)

```sql
CREATE TABLE IF NOT EXISTS execution_attempts (
    execution_attempt_id TEXT PRIMARY KEY,
    business_key TEXT NOT NULL UNIQUE,          -- "{position_id}:{side}:{seq}"
    idempotency_key TEXT NOT NULL UNIQUE,       -- sha256 of the canonical request
    position_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    mode TEXT NOT NULL CHECK (mode IN ('PAPER', 'SHADOW')),
    executor_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PREPARED', 'SUBMITTED', 'TERMINAL')),
    terminal_state TEXT CHECK (terminal_state IS NULL OR terminal_state IN (
        'REJECTED_BEFORE_SEND', 'DROPPED_OR_EXPIRED_NOT_PROCESSED',
        'LANDED_FAILED', 'LANDED_SUCCESS', 'UNKNOWN_REQUIRES_RECONCILIATION')),
    requested_notional_usd_dec TEXT,
    requested_qty_dec TEXT,
    realized_qty_dec TEXT,
    realized_notional_usd_dec TEXT,
    realized_unit_price_usd_dec TEXT,
    fee_usd_dec TEXT,
    external_ref TEXT,
    error_class TEXT,
    reconciliation_reference TEXT,
    observation_sha256 TEXT,
    prepared_at TEXT NOT NULL,
    submitted_at TEXT,
    terminal_at TEXT,
    reconciled_at TEXT
);
```

Positions gain `entry_attempt_id`, `exit_attempt_id`.

### 9.2 API

`prepare_entry_attempt(position_id, *, executor_id)`, `prepare_exit_attempt(position_id, *, executor_id)`,
`mark_attempt_submitted(attempt_id, *, submitted_at, external_ref=None)`,
`apply_execution_observation(attempt_id, observation)`, `reconcile_attempt(attempt_id, observation)`.
The runner flow: `accept_signal_decision(..., skip_fill=True)` → prepare → submitted → executor → observation.
The immediate simulated path (`accept_signal_decision` without `skip_fill`, `apply_paper_*_fill`) stays as
the simulator shortcut and writes no attempts.

### 9.3 Observation validity (mirrors the canonical per-state CHECKs)

| terminal_state | Attempt status before | Realized qty/notional/price | Fee | error_class | reconciliation_reference |
| --- | --- | --- | --- | --- | --- |
| REJECTED_BEFORE_SEND | PREPARED | forbidden | forbidden | required | forbidden |
| DROPPED_OR_EXPIRED_NOT_PROCESSED | SUBMITTED | forbidden | forbidden | required | forbidden |
| LANDED_FAILED | SUBMITTED | forbidden | allowed (≥ 0) | required | forbidden |
| LANDED_SUCCESS | SUBMITTED | required (> 0) | required (≥ 0) | forbidden | forbidden |
| UNKNOWN_REQUIRES_RECONCILIATION | SUBMITTED | forbidden | forbidden | required | required |

### 9.4 Position mapping

| Side | terminal_state | Position move |
| --- | --- | --- |
| BUY | LANDED_SUCCESS | ATTEMPTING → OPEN (economics from observation; realized notional ≤ admitted) |
| BUY | REJECTED_BEFORE_SEND | INTENT_CREATED → CANCELLED |
| BUY | DROPPED_OR_EXPIRED_NOT_PROCESSED, LANDED_FAILED | ATTEMPTING → CANCELLED (fee kept on the attempt) |
| BUY | UNKNOWN_REQUIRES_RECONCILIATION | ATTEMPTING → UNKNOWN |
| BUY | reconcile UNKNOWN → LANDED_SUCCESS / not landed | UNKNOWN → OPEN / CANCELLED |
| SELL | LANDED_SUCCESS | EXITING → CLOSED → RECONCILED (PnL with actual fee) |
| SELL | REJECTED_BEFORE_SEND | stays EXIT_REQUIRED |
| SELL | DROPPED_OR_EXPIRED_NOT_PROCESSED, LANDED_FAILED | EXITING → EXIT_REQUIRED (retryable) |
| SELL | UNKNOWN_REQUIRES_RECONCILIATION | EXITING → UNRESOLVED (+ `RECONCILIATION` result `UNRESOLVED`) |
| SELL | reconcile UNRESOLVED → LANDED_SUCCESS / not landed | UNRESOLVED → RECONCILED / EXIT_REQUIRED |

### 9.5 Canonical alignment (OD-2 default)

Same `terminal_state` enum, `business_key` / `idempotency_key` semantics, `submitted_at`, `terminal_at`,
`error_class`, `reconciliation_reference`. Documented divergences: USD decimals instead of atomic amounts;
`external_ref` generalizes `transaction_signature`; `fee_usd_dec` instead of lamport fee fields;
reconciliation updates the attempt in place and records `EXECUTION_ATTEMPT_RECONCILED` (history in
`execution_events`) instead of appending revision rows. A future live adapter maps its fills into
this seam and, in a separate atom, writes canonical rows to the research plane.

## 10. Optional A6 — unresolved-inventory entry veto

Policy field `unresolved_inventory_entry_veto ∈ {OFF, STRATEGY, GLOBAL}`, absent = `OFF`. The field is
stored and hashed only when ≠ `OFF`, so every existing revision keeps its `policy_sha256`. Admission
blocks with `BLOCK_UNRESOLVED_INVENTORY` when the scope holds any `UNKNOWN`, `EXIT_REQUIRED`, `EXITING`
or `UNRESOLVED` position. `OFF → STRATEGY/GLOBAL` = TIGHTENING; the reverse = RELAXATION.

## 11. Delivery plan

```text
A1 PAPER_PLANE_WRITE_INTEGRITY_V1          (S, SOL_XHIGH)  primitives: atomic + conditional + causal
A2 PAPER_SHADOW_ENTRY_INTENT_INTEGRITY_V1  (M, SOL_XHIGH)  CANCELLED, stop dominance, no auto-fill, binding
A3 DECISION_IDENTITY_AND_LINEAGE_GATES_V1  (S, LUNA_MAX)   as_of, fingerprint, spec drift, exit identity
A4 PAPER_PLANE_READ_FRESHNESS_V1           (XS, LUNA_MAX)  WAL-aware readonly, GET purity kept
A5 EXECUTION_ATTEMPT_SEAM_V1               (M, SOL_XHIGH)  attempt ledger + observation mapping (owner go)
A6 UNRESOLVED_INVENTORY_ENTRY_VETO_V1      (S, LUNA_MAX)   only if OD-1 asks for it
```

Order rationale: A2 adds transitions and cancel paths, so it builds on A1's atomic primitives. A3 and A2
both edit `accept_signal_decision`; they stay sequential. A4 is independent. A5 needs A2's `CANCELLED`
and A1's atomicity.

One vertical acceptance module serves the series:
`tests/test_paper_shadow_execution_integrity_vertical_v1.py` (created in A1, declared in
`configs/execution_domain_v1.json` → `required_fast_test_modules`; each atom adds one class).

Per-atom loop (every contract embeds its concrete form):

```text
bind + baseline -> red vertical tests reproduce the finding -> minimal fix -> focused green
-> execution-domain suite (14 modules + handoff) -> stochastic/crash proofs where relevant
-> contracts + catalog propagation -> isolated critics -> finish -> bind-evidence -> preflight-push
-> ONE PR -> exact-head CI -> merge-readiness -> owner phrase -> guarded merge -> post-merge readback
```

Series journeys covered by the module: J1 happy path (handoff shape), J2 entry UNKNOWN → reconcile (A5),
J3 exit no-route → UNRESOLVED → RECONCILED, J4 stop with in-flight intent → STOPPED (A2), J5 crash →
restart → retry (A1).

## 12. Traceability

| Finding | Invariant | Atom | Test class |
| --- | --- | --- | --- |
| F5, F6, F7 | INV-1..4 | A1 | `WriteIntegrityTests` |
| F1, F2, F3, F4 | INV-5..8, INV-13 | A2 | `EntryIntentIntegrityTests` |
| F8, F9 | INV-9, INV-10 | A3 | `DecisionIdentityGateTests` |
| F10 | INV-11 | A4 | `ReadFreshnessTests` |
| F11, F12 | INV-12 | A5 | `ExecutionAttemptSeamTests` |
| G1 | policy | A6 | `UnresolvedInventoryVetoTests` |

## 13. Operations and rollback

- Every schema change is additive (`_ensure_column`, `CREATE TABLE IF NOT EXISTS`); old stores open and
  migrate on first writable open; backups remain file copies.
- The VPS SHADOW heartbeat (legacy v1.0 `run_shadow_tick` over a fixture) keeps working; after A3 it
  fails closed with `STRATEGY_SPEC_DRIFT` if the commissioning strategy file changes without a version bump.
- Rollback of any atom: revert its merge commit. Added columns and the attempts table are ignored by
  older code.

## 14. Explicit non-goals (series)

Runner, activation registry, providers and quotes, LIVE, wallet, signer, canonical DuckDB writes,
Workbench UI redesign, VPS deployment, changes to `OPEN_RISK_STATES` semantics (except through A6),
partial-quantity support, v1.0 commissioning behavior.
