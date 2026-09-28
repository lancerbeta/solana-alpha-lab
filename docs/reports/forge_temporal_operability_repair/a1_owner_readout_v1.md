# FORGE_TEMPORAL_OPERABILITY_REPAIR_V1 owner readout

Head: pending-bind

## Closed this increment (P1-A / P1-B)

- P1-A: `SNAPSHOT_ROW_INTERPRETATION_V1` admits legacy rows without explicit policy when occurrence/request/acquisition lineage is complete; insufficient lineage surfaces `SNAPSHOT_LINEAGE_UNINTERPRETABLE` instead of a false empty population. New and legacy published bytes share one journal→DocumentRunner scientific payload (observed/mean/spec/policy/exclusions).
- P1-B: authorized selected repair skips slot re-reservation, uses disposition-scoped artifact ids, projects repair marker into list/bundle, allows capability/execution lineage under repair, and reaches selected freeze→critic→finalize with sticky replay. NO_WORTHY repair path retained.

## Vertical receipts (local disposable)

- Vertical A new+legacy: observed_target_n=1, mean≈0.2, DocumentRunner COMPLETE, provider_calls_actual=0, journal==consumer scientific fields.
- Vertical B NO_WORTHY: 2 MAIN + preview → apply → third MAIN → new terminal → close.
- Vertical B selected: historical parent → repair → new capability freeze → KILL terminal ≠ parent NO_WORTHY → sticky replay; mains stay 3.

## Metadata-only live cohort note

Current cohort bindings/schema are not re-run against live S3 in this atom. Compatibility for sealed partitions with complete transport lineage is proven on fixtures; live corpus without occurrence/request remains UNKNOWN until a separate metadata read.

## Unexecuted post-merge plan

1. Metadata-only live readiness read of current parent inventory (no apply).
2. Owner-authorized repair-continuation-plan for the live parent only after separate authority.
3. No merge in this atom.

## Non-claims

NO_LIVE_APPLY, NO_MARKET_FORGE, NO_MERGE, NO_ALPHA.
