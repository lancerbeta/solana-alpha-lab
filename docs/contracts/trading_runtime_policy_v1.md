# TradingRuntimePolicy V1

Owner-authorized PAPER/SHADOW operating envelope over existing PaperPlane.
Does not own StrategyVersion meaning, scientific evidence, LIVE authority,
wallet/equity truth, or Workbench writes.

Catalog document: `DOC-TRADING-RUNTIME-POLICY-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (existing; no new route)
Storage owner: PaperPlaneStore (`paper_plane_state.sqlite`)

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

Admission freezes `admitted_entry_notional_usd_dec` and policy
mode/revision/sha256. Later policy revisions do not resize existing
admissions. Actual entered notional remains a separate fill field.

Relevant OPEN_RISK unknown required notional → `RUNTIME_EXPOSURE_UNKNOWN`
→ BLOCK. Historical CLOSED/RECONCILED missing notional does not block.

## 7. Operator path

Agent uses SHOW → CHECK → DIFF → exact owner authorization → APPLY →
READBACK. No Workbench policy editor in V1. Rollback appends a new
revision with previous policy content. Same idempotency key + same
request produces one revision. Stale current hash →
`POLICY_STALE_WRITE_DENIED`.

`new_entries_enabled=false` is the gitless emergency stop for NEW
admissions in that mode. Existing per-bot `PAUSE_NEW_ENTRIES` remains.

## 8. GET / persistence

Workbench GET never creates the policy table, a revision, or a SQLite
file. Policy APPLY is the only enablement path.

Policy revisions live inside `paper_plane_state.sqlite`, already on the
mutable backup source list. Ordinary Workbench/service restart and
exact-SHA deploy do not reset current policy. Rollback appends; it
never deletes history.

LIVE cannot resolve TradingRuntimePolicyV1 as authority.
