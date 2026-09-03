# FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1 — owner readout

## Decision unlocked

Can a future promoted hypothesis hand an already frozen decision into one stable
PAPER/SHADOW execution runtime **without** the runtime knowing hypothesis feature
names or scientific rule implementation?

**Answer: YES** — via StrategyVersion v1.1 + SignalDecision/ExitDecision.

## What landed

- `StrategyVersion v1.1` schema: no scientific feature enums / threshold syntax
- `SignalDecision v1` / `ExitDecision v1` contracts
- `strategy_runtime.py`: v1.0/v1.1 dispatch + validation
- `paper_plane.py` v1.1 path: activation_epoch binding, signal-id position identity,
  max_age / max_open enforcement, exit → `EXIT_REQUIRED` without fill claim,
  SHADOW uses `SHADOW_EXECUTABLE`, fail-closed lineage on replay
- Legacy v1.0 commissioning path preserved (`signal_kind_for` only on v1.0)
- Idempotent SQLite additive migration for v1.1 lineage columns

## Proof

Focused suite `tests/test_factory_strategy_execution_boundary_v1.py` (21) + legacy
`tests/test_early_state_to_paper_vertical_slice.py` (19) = 40 PASS.

Two structurally different producers (threshold vs pattern) emit `SignalDecision`
outside the engine; engine stays feature-name agnostic.

Terminal: `STRATEGY_EXECUTION_BOUNDARY_PASS`

## Non-claims

- No alpha, NetReturn, live fill, provider calls, PnL dashboard, or micro-live
- No autonomous strategy generation

## Next

Atom 2 of pack: `PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1` (after merge read-back
and unless a due research/time gate preempts).
