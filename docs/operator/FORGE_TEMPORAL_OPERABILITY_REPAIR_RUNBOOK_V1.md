# Forge temporal operability repair — operator runbook

Capability: `FORGE_TEMPORAL_OPERABILITY_REPAIR_V1`.
Repair capability id: `CAP-HFIC-TEMPORAL-OPERABILITY-REPAIR-001`.

## What changed

1. Bound schedules may declare per-point `(due_offset, allowed_lateness)`.
   The query scalar remains the **X300 envelope**; other points may differ.
2. Temporal queries may set
   `schedule.observation_clock_policy: PROVIDER_REPORTED_SNAPSHOT_V1`.
   Exits then use request/response/availability clocks. Member anchor is not a
   market-event timestamp. Source price event time stays `UNKNOWN` unless
   proven.
3. Result / readout carry `observation_clock_policy` and
   `target_exclusion_reasons` (pooled + by_cohort).
4. After a completed `NO_WORTHY` without selected candidate, an owner-authorized
   append-only repair continuation may resume the same slot on the **spent**
   look ledger. Plan is no-write; apply is separate and idempotent.

## Compatibility

- Legacy uniform `schedule_lateness_seconds` without point maps still requires
  scalar equality.
- Default / omitted clock policy keeps prior `EVENT_TIME_V1` identity bytes.
- Raw observation `event_time` is not globally rewritten for other consumers.
- Unknown disposition / policy must stop explainably; it must not silently
  return the old DONE as a free new search.

## Live parent (post-merge, separate authority)

1. No-write `plan_repair_continuation` against the exact parent
   run/session/slot/terminal hashes and remaining budget.
2. Only after explicit apply authority: synthetic-proven apply path on that
   parent (not part of this delivery atom).
3. One ordinary temporal query inside the inherited remainder, with
   `PROVIDER_REPORTED_SNAPSHOT_V1` and mixed point clocks as needed.
4. Readback. Do not promise a worthy candidate.
