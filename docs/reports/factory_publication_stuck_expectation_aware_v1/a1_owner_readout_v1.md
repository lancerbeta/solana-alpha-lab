# FACTORY_PUBLICATION_STUCK_EXPECTATION_AWARE_V1 — owner readout

## Decision unlocked

Does Telegram `PUBLICATION_STUCK` mean «публикацию ждали, а она не пошла»,
а не «6 часов ничего не публиковалось, хотя публиковать было нечего»?

**Answer: YES** in Git. This is not product DONE, not alpha, and not a
Factory deploy.

## What landed

`RDP_PUBLICATION_STALE` now requires a current publication obligation from
existing packet truth:

- `due_now_count`, `claimed_count`, `actually_overdue_count`, `in_flight_count`
- `publication_jobs_open_count`

Tri-state: `PUBLICATION_EXPECTED` | `PUBLICATION_NOT_EXPECTED` |
`PUBLICATION_EXPECTATION_UNKNOWN`.

Proven idle (including future-not-due > 0) suppresses stale even after 6h or
24h. Missing/malformed expectation evidence fails closed and keeps the old
conservative 6h / missing-marker behavior. Watch grace, dedupe, RECOVERED,
`.published` mtime source, 6h bound, collector/publisher/lease are unchanged.

## Proof

Focused unittest matrix A–L in
`tests/test_factory_unattended_operability_closure_v1.py` plus the PR #273
`DATA_STALE` ↛ `COLLECTOR_STALLED` invariant. Isolated critics after content
freeze. Exact-head CI is the remaining machine gate. No VPS mutation.

## Non-claims

- No production deploy
- No incident clear, Telegram emit, timer/HOT90/backup/Drive
- No collector scheduling or scientific publication change
- No canonical DONE / alpha / NetReturn

## Stop

Owner merge phrase after exact-head CI and `ready_for_owner_phrase=true`.
Deployment is a later OPERATE decision against a chosen target SHA, not
«latest main».

## Rollback

Ordinary Git revert of this branch. Live Factory stays on its current
deployed SHA until a separate deploy atom.
