# TASK-36 RC002 H11 lifecycle-clock mechanism screen contract v1

## Decision

Open a new task-owned research cycle `RESEARCH-CYCLE-RC002-001` and run
one frozen exploratory mechanism screen of H11: whether
lifecycle-relative clocks (`time_since_migration`,
`time_since_decision_time_running_peak`) add stable out-of-sample
information about subsequent post-migration outcomes beyond a
predeclared coarse UTC/session baseline.

Do not start H13 or H02. Do not build a generic prospective collector.
Do not retrofit H11 into frozen RC-001. Deprioritize remaining RC-001
families while this screen runs. Preserve every RC-001 definition,
negative result and hash.

## Frozen protocol

Bound in `configs/task36_rc002_h11_lifecycle_clock_screen_v1.yaml`
before any outcome inspection:

- family `H11_LIFECYCLE_CLOCK`
- stage `EXPLORATORY_MECHANISM_SCREEN`
- data semantics `RETROSPECTIVE_EVENT_TIME_RECONSTRUCTION`
- `live_PIT_claim: false`
- `execution_claim: false`
- universe: confirmed post-migration pools from an outcome-independent
  contiguous window; include fast deaths, inactive paths and typed gaps
- no parameter search, no ML search, no missing-to-zero
- chronological / group-aware split, never random rows
- no conversion of retrospective `event_time` into live
  `available_to_strategy_at`

The exploratory trial is registered `PENDING` before outcome values are
read. RC-001 holdout consumption stays empty.

## Adopted historical routes

The live universe is reconstructed only from already-tracked receipts:

- TASK-08 lifecycle discovery probe
- TASK-09 PumpSwap touch probe
- TASK-21 effective sample (outcomes remain unopened)
- TASK-30 A24 retrospective panel

No new provider, credential, paid plan, wallet, signer, transaction or
deployment authority.

## Terminal outcomes

- `H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE`
- `H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION`
- `H11_SCREEN_INCONCLUSIVE_DATA_SCALE`
- `HISTORICAL_ROUTE_INADEQUATE_REPLAN`
- `STOP_INTEGRITY_CONFLICT`

Infrastructure without a research or data decision is not success.

## Non-claims

No alpha, NetReturn, fillability, strategy, bot, RC-001 mutation,
entity graph, route-feasibility panel, wallet, cockpit, deployment or
unattended collector. Synthetic protocol tests are not the live
universe.
