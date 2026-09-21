# COLLECTOR_CAMPAIGN_CONTINUITY_REPAIR_V1 — owner readout

## Outcome

Git/mainline repair so a missed in-window rollover does not force a multi-hour
admission blackout, doctor/status show the current ACTIVE/DRAINING campaign
(not a historical ABORTED_SAFETY), and Telegram/operability emits one deduped
`CAMPAIGN_SUCCESSOR_REQUIRED` warning inside the final 24h when no successor is
prepared.

## What changed

- Late post-window successor activate allowed when predecessor is proven
  NON_ADMITTING (DRAINING + closed admission); no rollover row required;
  successor `starts_at` must be forward from the append-only DRAINING
  transition event's effective time and no later than activation; backdated
  windows denied; one admitting family preserved. Doctor exposes
  `late_recovery_at` and `late_recovery_proof` for the owner; missing proof
  remains fail-closed with an explicit recovery next action.
- Current-activation selection: ACTIVE → DRAINING → freshest otherwise.
- Pre-expiry continuity proof accepts only a live authorized window covering
  the current admission boundary or a valid rollover; historical/post-gap
  schedules remain attention. `CAMPAIGN_SUCCESSOR_REQUIRED` renders as a
  deduped owner attention (`FACTORY / ATTENTION — ACTION`,
  `MESSAGE_TYPE=ATTENTION`, `ATTENTION=CAMPAIGN_SUCCESSOR_REQUIRED`), not an
  incident; `SOURCE_DATA_STALE` unchanged
  (`age > period*3`).

## Explicit non-claims

- No VPS deploy / live ACT-E0CC mutation / provider calls / auto-authorize.
- No SQLite schema migration / history rewrite / today's gap backfill.

## Next operator step (separate atom)

Deploy repaired main, prepare/authorize a forward successor, activate after
admission close if still needed.
