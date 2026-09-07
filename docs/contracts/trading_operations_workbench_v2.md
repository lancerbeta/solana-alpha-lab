# Trading Operations Workbench V2

Owner-facing composition of existing PAPER/SHADOW operations. Does not own
StrategyVersion meaning, PaperPlane state machine, science handoff, Visual
OS, System runbooks, or future Risk/Economics contracts.

Catalog document: `DOC-TRADING-OPERATIONS-WORKBENCH-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (existing; no new route)
Lower-level capability: `OWNER_OPERATIONS_COCKPIT_V1` (consumed, not replaced)

```text
authority_granted = false
activation_created = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
GET = non-mutating
Git StrategyVersion = definition, not runtime
```

## 1. Owner questions

```text
Что сейчас действительно исполняется и какой риск остаётся?
Почему по этому объекту произошло именно это и где путь остановился?
Что мне сейчас безопасно сделать и что реально изменилось?
```

## 2. Truth planes

```text
PRODUCT / STRATEGY MEANING     → Git StrategyVersion
SCIENCE                        → Git + ResearchStore
CURRENT BOT / POSITION / CMD   → PaperPlane + operator_commands
HOST / DEPLOY HEALTH           → outside this surface
OWNER PRESENTATION             → derived Workbench projection
```

LifecycleProjection / Workbench persist nothing.

## 3. GET non-mutation

GET `/`, `/research`, `/operations`, `/economics`, `/system` must cause:

```text
0 new SQLite files
0 new runtime directories
0 runtime rows
0 execution events
0 operator-command records
0 Git mutation
```

Absent PaperPlane:

```text
source_status = NOT_PRESENT
```

not `bots = 0`. A command against absent PaperPlane fail-closes
(`SOURCE_NOT_PRESENT`) and does not create the store.

## 4. Observe

Each operational context exposes strategy_id / version, mode, activation
epoch, bot_instance_id, bot status, entries_paused, times, open/partial/
unknown/exit-required/unresolved counts, current blocker, next safe action.

Git StrategyVersion without activation/bot is `ACTIVATION_GAP`, never an
empty running bot.

## 5. Diagnose

Proven stages only, joined by explicit `signal_decision_id` then
`position_id`. Never mint-only, time proximity, filename or narrative.

```text
SIGNAL ≠ RISK ALLOW ≠ INTENT ≠ OBSERVATION ≠ FILL ≠ CLOSED ≠ RECONCILED
```

Missing stage: `GAP` / `UNKNOWN`. Historical events without join keys:
`LEGACY_TRACE_GAP`.

## 6. Act & verify

Reuse: `PAUSE_NEW_ENTRIES`, `RESUME_NEW_ENTRIES`, `REQUEST_CLOSE_POSITION`,
`REQUEST_CLOSE_ALL`, `STOP_BOT`.

Each surfaced command names TARGET, CURRENT PRECONDITION, EXPECTED EFFECT,
FAIL-CLOSED CONDITION, IDEMPOTENCY, POST-ACTION READBACK.

HTTP 200 / button click is not proof. Fresh projection after the domain
command is the proof. Routine command must not mutate Git.

No `START PAPER` / `START SHADOW` / `ACTIVATE STRATEGY` on this surface.
Missing accepted activation contract: `ACTIVATION_PATH_GAP`.

## 7. Local blockers

```text
SOURCE_NOT_PRESENT
POSITION_UNKNOWN
EXIT_REQUIRED
UNRESOLVED_POSITION
PNL_UNKNOWN_OR_STALE
BOT_DRAINING
ENTRIES_PAUSED
RISK_BLOCK
SIGNAL_TRACE_GAP
ACTIVATION_GAP
STALE_OPERATOR_SNAPSHOT
RUNTIME_SOURCE_UNAVAILABLE
WATCHLIST_SOURCE_GAP
ACTIVATION_PATH_GAP
```

No global attention database. No VPS diagnosis from `/operations`.

## 8. Economics / system

Retain source-owned operational metrics only. No owner FCF, LIVE
NetReturn, or capital allocation. `/operations` may say
`RUNTIME_SOURCE_UNAVAILABLE`; it must not say the VPS is unhealthy.

## 9. Watchlist

If no canonical pre-signal watch source exists: `WATCHLIST_SOURCE_GAP`.
Do not invent storage. This gap does not block the three primary loops.
