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
  backdated successor windows denied; one admitting family preserved.
- Current-activation selection: ACTIVE → DRAINING → freshest otherwise.
- Pre-expiry attention via existing incident dedupe; `SOURCE_DATA_STALE`
  unchanged (`age > period*3`).

## Explicit non-claims

- No VPS deploy / live ACT-E0CC mutation / provider calls / auto-authorize.
- No SQLite schema migration / history rewrite / today's gap backfill.

## Next operator step (separate atom)

Deploy repaired main, prepare/authorize a forward successor, activate after
admission close if still needed.
