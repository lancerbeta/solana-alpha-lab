# TradingRuntimePolicy V1

Owner-authorized PAPER/SHADOW operating envelope over existing PaperPlane.
Does not own StrategyVersion meaning, scientific evidence, LIVE authority,
wallet/equity truth, or Workbench writes.

Catalog document: `DOC-TRADING-RUNTIME-POLICY-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (existing; no new route)
Storage owner: PaperPlaneStore (`paper_plane_state.sqlite`)

The ordinary offline runner uses the same policy/admission owner and frozen
revision/notional/fee bindings: `docs/contracts/episode_decision_continuity_v1.md`.
Entry-admission count, possible inventory, operator-settled and drain-clear
remain distinct. Correcting a consumer count does not add EXIT_*/UNRESOLVED to
the historical entry-risk basis. The ordinary operating profile additionally
checks the versioned outstanding-obligation basis below. A pending entry is rechecked for pause/stop/stale/invalid policy
before a modeled attempt. Exit reconciliation remains available during drain.

```text
authority_granted = false
LIVE = NOT_SUPPORTED
GET = non-mutating
Git StrategyVersion = requested/declared execution
TradingRuntimePolicy = additional runtime overlay
current policy values never enter Git/Catalog
```

## 1. Owner questions

```text
Что сейчас действительно активно, какой риск открыт,
что блокирует новые входы и что я могу безопасно сделать без Git?
```

## 2. Truth planes

```text
PRODUCT / STRATEGY MEANING     → Git StrategyVersion
SCIENCE                        → Git + ResearchStore
CURRENT RUNTIME ENVELOPE       → TradingRuntimePolicyV1 in PaperPlane
BOT / POSITION / INVENTORY     → PaperPlane
OPERATOR COMMAND / IDEMPOTENCY → operator_commands
HOST / DEPLOY HEALTH           → System
ECONOMIC INTERPRETATION        → RISK_AND_ECONOMICS_V1 (read-only)
OWNER PRESENTATION             → Workbench
```

Hard invariants:

```text
StrategyVersion != runtime capitalization
Git config != current runtime setting
Runtime policy != scientific evidence
Runtime policy != LIVE authority
Workbench GET != writer
```

## 3. Mode scope

V1 modes: `PAPER`, `SHADOW`. Each has an independent revision chain.
PAPER inventory does not consume SHADOW limits and vice versa.
LIVE cannot resolve this policy as authority. Future LIVE needs a
separate owner-authorized contract and does not inherit PAPER/SHADOW.

## 4. Bootstrap

Missing table or missing current row:

```text
RUNTIME_POLICY_STATUS = NOT_CONFIGURED_STRATEGY_ONLY
```

Existing StrategyVersion-only admission continues. Creating the schema
does not enable guessed limits. First real policy is an owner-authorized
OPERATE APPLY.

Invalid/corrupt current row:

```text
RUNTIME_POLICY_INVALID
```

NEW admissions fail closed. EXIT / reconciliation remain possible.

## 5. Sizing

```text
strategy_requested_notional = StrategyVersion.notional_policy.notional_usd
runtime_entry_cap = strategy override ELSE mode-global ELSE none
effective_entry_notional = min(strategy_requested, runtime_cap if configured)
```

Runtime never increases the StrategyVersion request.
Portfolio/strategy/mint notional caps are admission ceilings, not a
dynamic sizing model. Remaining headroom below order size → BLOCK,
never auto-shrink.

V1 capital limits are entry-risk notional limits, not wallet cash,
equity, VaR, or Owner FCF.

## 6. Admission

One serialized SQLite `BEGIN IMMEDIATE` boundary evaluates
StrategyVersion + current policy + current inventory together.
OPEN_RISK_STATES semantics are unchanged. Same SignalDecision retries
resume one Position identity and do not consume a second slot.

StrategyVersion `max_open_positions` remains bot-local, matching the
pre-overlay PAPER/SHADOW admission counter. Runtime strategy position
and notional caps are keyed by `strategy_id` across the mode so a new
StrategyVersion cannot double the family budget. Absent policy
(`NOT_CONFIGURED_STRATEGY_ONLY`) therefore does not change overlapping
activation-epoch admission. Missing `strategy_id` on a relevant OPEN_RISK
row fail-closes family runtime caps (`RUNTIME_EXPOSURE_UNKNOWN`),
including strategy-family notional caps, not only position-count caps.

Owner projection must not mix those scopes into one scalar: family
inventory is shown against the runtime family cap (`NOT_SET` when
absent); StrategyVersion max is labeled bot-local.

Admission freezes `admitted_entry_notional_usd_dec`, `admitted_fee_bps`,
and policy mode/revision/sha256. Later policy revisions do not resize
existing admissions. Actual entered notional remains a separate fill field.
A fill whose fee differs from `admitted_fee_bps` is
`ENTRY_FILL_FEE_MISMATCH`. A notional above the frozen admission is
`ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION`.

Resume of an admitted pre-attempt intent re-checks staleness, bot status,
pause, policy validity and `new_entries_enabled`, in that order. A match
cancels the intent with a reason and raises the same block code. `ATTEMPTING`
and `UNKNOWN` never auto-fill; the retry answers `reconciliation_required`.
PRE_TRADE_RISK_SNAPSHOT records StrategyVersion bot-local max and
runtime family max as separate fields; it does not emit a mixed-scope
minimum as canonical capacity.

Relevant OPEN_RISK unknown required notional → `RUNTIME_EXPOSURE_UNKNOWN`
→ BLOCK. Historical CLOSED/RECONCILED missing notional does not block.

## 6.1 Ordinary operating envelope: outstanding obligations V1

The optional ordinary profile stores an append-only, hash-linked
`smial.ordinary-operating-envelope` v1.0 event in the same PaperPlane database.
It requires two explicit positive bounds: `max_outstanding_positions` and
`max_outstanding_cost_basis_usd`. Missing configuration is
`CONFIGURATION_REQUIRED` for an ordinary caller; legacy APIs retain their
StrategyVersion/runtime-policy entry-risk semantics and original hashes.
These bounds are operating cost basis, never wallet cash, equity, VaR or a
scientific risk estimate. Configuration takes authority from its enclosing
explicit operator/profile command; the storage helper grants none.

`OUTSTANDING_OBLIGATIONS_V1` counts all identities and activation epochs in
one mode: unattempted reservations, possible entries, known inventory,
partial remainder, `EXIT_REQUIRED`, `EXITING`, and unreconciled inventory.
PAPER and SHADOW stay independent. Unattempted cancellation, definitive entry
non-fill, or a proved complete exit releases the physical obligation.
`CLOSED` alone does not. Missing identity/exposure or an unresolved attempt
is `OUTSTANDING_OBLIGATIONS_UNKNOWN` and vetoes new entries. A possible entry
retains at least its admitted cost basis; an uncertain exit retains the last
proved remaining inventory. Unknown fees/costs are shown separately and do
not invent inventory after a proved complete exit.

The admission check and frozen reservation share `BEGIN IMMEDIATE` with the
existing risk owner. It may only deny, never enlarge or auto-shrink the
accepted amount. A predecessor using the full mode bound still consumes it
after switching the entry-active identity. A confirmed partial exit reduces
capacity by its proved residual cost basis; a new request above headroom is
denied unchanged. Before ENTRY attempt the same check excludes that attempt's
existing reservation, includes every other obligation, and rechecks current
envelope/control. Exit/reconciliation remains available during safety veto.

Existing owner API: `normalize_operating_envelope`,
`configure_operating_envelope` (compare-and-swap plus command idempotency),
`read_operating_envelope`, `obligation_summary`, `enforce_operating_envelope`.
`accept_signal_decision_outcome(..., ordinary_operating=True)` adds the atomic
ordinary check. `begin_modeled_attempt` repeats it for the frozen ordinary
reservation. No competing inventory table or risk engine is introduced.
Indexed event-type/position queries read the envelope revision chain and the
original witnesses of current and terminal position candidates. Terminal
release requires verified attempt/FINAL/result, so SQL work grows linearly
with terminal positions; O(outstanding) is not claimed. Unrelated journal
growth does not require a full journal scan. Legacy readonly stores without
the additive columns retain their compatible read fallback.

## 7. Operator path

Agent uses SHOW → CHECK → DIFF → exact owner authorization → APPLY →
READBACK. No Workbench policy editor in V1. Rollback appends a new
revision with previous policy content. Same idempotency key + same
request produces one revision. Stale current hash →
`POLICY_STALE_WRITE_DENIED`.

`new_entries_enabled=false` is the gitless emergency stop for NEW
admissions in that mode and also cancels admitted, unattempted intents
(`NEW_ENTRIES_DISABLED`). Existing per-bot `PAUSE_NEW_ENTRIES` remains and
cancels those same intents (`ENTRIES_PAUSED`).

### Decision identity

A SignalDecision is accepted only with an explicit `as_of`. `decision_at` more
than 2 seconds after `as_of` is `SIGNAL_DECISION_FROM_FUTURE`. One
`signal_decision_id` binds one canonical body: a different body, or any
non-ENTER decision, under an id that already owns a position is
`SIGNAL_DECISION_IDEMPOTENCY_MISMATCH`. Legacy rows with a NULL fingerprint
skip the ENTER comparison. `start_bot` stores `strategy_spec_sha256`,
backfills NULL, and raises `STRATEGY_SPEC_DRIFT` when stored and loaded
hashes differ. An ExitDecision whose `strategy_version` differs from
`positions.strategy_version_label` is `EXIT_POSITION_VERSION_MISMATCH`.
Positions keep `signal_decision_sha256`, `strategy_spec_sha256` and a
separate `exit_reason_code`; entry `reason_code` is not overwritten.
`SIGNAL_DECISION_ACCEPTED` carries the fingerprint and evidence refs.
`EXIT_DECISION_ACCEPTED` is a `POSITION` stage event.

## 8. GET / persistence

Workbench GET never creates the policy table, a revision, or a SQLite
file. Policy APPLY is the only enablement path.

Policy revisions live inside `paper_plane_state.sqlite`, already on the
mutable backup source list. Ordinary Workbench/service restart and
exact-SHA deploy do not reset current policy. Rollback appends; it
never deletes history.

Cold recovery must retain the current original operating-envelope events and
runtime-policy revisions, including changes after backup. A complete cut
binds their full chains and committed heads. Reconciliation preserves exact
original identities, clocks and lineage; it never re-authorizes an old policy
through a new configure command. Missing, damaged, foreign or conflicting
authority retains the restore fence. A valid later local extension is not
replaced by an older cut. Inventory ACK and RESUME cannot substitute current
configuration reconciliation or restore a less restrictive backup limit.

LIVE cannot resolve TradingRuntimePolicyV1 as authority.

Current ordinary readonly status resolves this same policy owner in its coherent
snapshot. VALID or intentional NOT_CONFIGURED_STRATEGY_ONLY are acceptable;
RUNTIME_POLICY_INVALID prevents READY and projects exact policy status/revision/SHA.
Invalid current policy does not fabricate UNKNOWN for independently verified old
positions or prevent their originating EXIT. OBSERVED current health uses physical
clock; synthetic virtual time and original activation/recovery timestamps remain
separate. Current status/check cannot use --as-of/clock-file to assert historical
input freshness as present readiness.
