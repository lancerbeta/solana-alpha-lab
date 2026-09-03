# PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1 — owner readout

## Decision unlocked

Is the single SQLite PAPER/SHADOW plane durable under ordinary position
management, UNKNOWN marks, pause/close-all, and restart?

**Answer: YES** — Decimal accounting + execution events + idempotent commands
on the same `paper_plane_state.sqlite`.

## What landed

- Additive store tables: `execution_events`, `operator_commands`, `position_marks`
- Decimal entry/exit accounting with explicit PAPER vs SHADOW evidence classes
- Derived projection: loss streak, max drawdown, open-set SHA256, attention cards
- Commands: pause/resume, close-one, close-all (stale snapshot denied), stop→DRAINING
- Smoke: `scripts/factory_paper_shadow_operator_smoke.py --json`

## Proof

Fixture PnL: +9.79 / −10.19 / −20.18 → streak=2, max_drawdown_usd=30.37.
Focused suite + smoke terminal `PAPER_SHADOW_ACCOUNTING_CONTROL_PASS`.
Provider/credential/wallet/cash = 0.

## Non-claims

- No UI cockpit (Atom 3), no alpha/NetReturn, no live fills, no second DB

## Next

Atom 3: `OWNER_OPERATIONS_COCKPIT_V1` after this merge read-back.
