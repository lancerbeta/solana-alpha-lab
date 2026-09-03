# OWNER_OPERATIONS_COCKPIT_V1 — owner readout

## Decision unlocked

Can the owner see PAPER/SHADOW inventory, bounded economics, and run Atom-2
operator commands from Workbench without Git/SQLite archaeology or a new UI
package?

**Answer: YES** — `/operations` and `/economics` are earned on the existing
stdlib Workbench via `FactoryApplication` only; MARKET stays hidden.

## What landed

- Nav/config/schema: HOME · RESEARCH · OPERATIONS · ECONOMICS · SYSTEM; MARKET hidden
- OPERATIONS: bots, counts, positions, attention, recent changes, operator forms
- ECONOMICS: bounded PAPER/SHADOW model metrics + explicit non-claims
- Commands: pause/resume, close-one, close-all (confirm + stale snapshot), stop→DRAINING
- Lazy paper-plane attach: RESEARCH/SYSTEM do not create SQLite; ops surfaces do

## Proof

Focused suite `tests/test_owner_operations_cockpit_v1.py` + updated cockpit lite
tests. Terminal `OWNER_OPERATIONS_COCKPIT_PASS` when operations projection is
attached. Provider/credential/wallet/cash = 0.

## Non-claims

- No live PnL/FCF/capital/NetReturn, no MARKET unhide, no alpha, no canonical DONE

## Stop

**STOP_THIS_CHAIN** after merge + post-merge read-back (pack Atom 3 terminal).
