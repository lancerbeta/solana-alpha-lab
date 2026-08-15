# TASK-37 RC002 H11 migration-clock capture contract v1

## Decision

After `HISTORICAL_ROUTE_INADEQUATE_REPLAN` on the TASK-36 H11 screen
(live N=0), reconstruct lifecycle clocks from the already-admitted
Helius `getTransactionsForAddress` pool-history batch using the pinned
Pump Create/Complete/CompletePumpAmmMigration decoder. Do not start
H13/H02. Do not open a second provider. Do not spend. Do not convert
retrospective event time into live PIT.

Keep research cycle `RESEARCH-CYCLE-RC002-001`. Do not retrofit into
frozen RC-001.

## Frozen clock definitions

Bound in `configs/task37_rc002_h11_migration_clock_capture_v1.yaml`
before any event inspection:

- `create_at` := `CreateEvent.timestamp` (chain event i64)
- `migration_at` := `CompletePumpAmmMigrationEvent.timestamp` (chain
  event i64). `CompleteEvent.timestamp` is `MIGRATION_STARTED` only and
  stays a typed gap, not a substitute migration clock
- `time_since_migration` := `decision_time - migration_at`
- `running_peak_at` := max price among events with `event_at <=
  decision_time`; future events are ignored
- forbidden sources for `migration_at`: later price, first PumpSwap
  trade, block-time heuristic, first-reliable-availability

Cohort selection is outcome-independent. Predeclared H11 minima remain
8 pools, 2 days, 2 deployers. Fast deaths, inactive paths and typed
gaps stay in the universe when clocks exist.

## Adopted route

One provider-route identity:
`HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001` targeting the already
captured A22/A23 PumpSwap **pool** address. Decode with the pinned
TASK-08 Pump event subset. No new RPC, credential, paid plan, wallet,
signer, transaction or deployment.

## Terminal outcomes

- `CLOCKS_RECONSTRUCTED_COHORT_READY`
- `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`
- `INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE`
- `STOP_INTEGRITY_CONFLICT`

Exact gap for the wrong-address outcome: Create and
CompletePumpAmmMigrationEvent are absent from the pool-history route.

## Non-claims

No alpha, NetReturn, fillability, strategy, bot, RC-001 mutation,
entity graph, route-feasibility/quote panel, wallet, cockpit,
deployment, unattended collector, live PIT or H11 effect re-screen.
Synthetic protocol tests are not the live universe.
