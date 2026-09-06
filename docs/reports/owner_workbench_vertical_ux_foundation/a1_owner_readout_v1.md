# OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1 — owner readout

## Decision unlocked

Can the five Workbench routes share one Russian-first Visual OS shell without a
frontend rewrite, a second visual system, or a change to command POST values?

**Answer: YES** for Petr on `/`, `/research`, `/operations`, `/economics`,
`/system`. This is not product DONE and not alpha.

## What landed

- One shell: signal rail, page H1 + question, facts, action, machine truth in
  `<details class="technical">`
- Russian-first labels; canonical EN tokens stay visible
- UNKNOWN is not `$0` or healthy; a live process is not «система исправна»
- Exact runtime glosses: `PRESENT` → «есть»; `RUNTIME_PROVED_BACKUP_UNKNOWN`
  is not «деградирован»
- Cycle `DO_NOT_PROMOTE` is visible on Home when attention is empty
- Research GET omits `git_archaeology_required` rather than inventing `false`
- Command POST values unchanged

## Proof

Focused unittest on five routes plus ordinary-hypothesis / operations / cockpit
consumers. Live Web-view in the delivery session at 1440×900 and 1920×1080
(Playwright is a non-goal; no screenshot dumps in Git). Isolated critics:
CODE PASS, GOAL/DoD PASS, ARCHITECTURE PASS
(`packet_fingerprint_sha256=24777a6f12c74e340964c91b7f38cfc992bbe03afaebbeb4bec8246ef8e2835f`).

## Non-claims

- No alpha, NetReturn, provider, wallet, VPS, StrategyVersion
- No canonical DONE
- Research archaeology note `UNKNOWN` means this GET omitted the field, not
  that the factory evaluated unknown

## Stop

Owner waived `MERGE_ORDER=SECOND`. Stop at `OWNER_ATTENTION_GATE_V2`. Next
named atom remains `SCIENCE_TO_STRATEGY_HANDOFF_V1` — do not auto-start.

## Rollback

Ordinary Git revert of `cursor/owner-workbench-vertical-ux-foundation-v1`.
No runtime reconciliation.
