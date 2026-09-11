# LIVE_COHORT_FIRST_FORGE_ENTRY_COMPAT_V1 — owner readout

## What closed

The already-visible software/schema blockers on
live ObservationSchedule → C1 closure → source → seal → verify →
split-host transport → local LIVE CORPUS import →
`FORGE_CONTROL_READY` are repaired in this atom.

This atom did **not** run live seal/import or `/hypothesis-forge`.

## Production shape

Live `candidate_members.payload_json` uses `discovery_available_at`.
Shared resolver accepts only equivalent representations:

1. `discovery_first_reliable_available_at`
2. `first_reliable_available_at`
3. `discovery_available_at`

`first_seen_at` is not admission. Missing/unparseable admission is unassignable.
Producer insert does not fabricate `discovery_available_at=now`.
Sampled members with missing or invalid admission fail closed
(`ADMISSION_CLOCK_MISSING` / `ADMISSION_CLOCK_INVALID`) instead of dropping
out of the denominator. Frozen C1 cutoff also includes completed C1
observation-panel `created_at` at or before `as_of`. Member identity binds
admission instant. CONTROL corpus identity is canonical `dataset_id`, and
`forge-control-ready` requires `lineage.current_dataset_manifest_id` match.

Cumulative MEMBER_BATCH is extracted row-level. Mixed C1+C2 may contribute
C1 rows; C2 rows never enter C1. Frozen C1 uses machine `closure_cutoff_at`.
Later C2 publication / producer SHA / global open-job count do not rewrite
C1 identity.

CONTROL `MAX_DATASETS=8` keeps a protected slot for current
`DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`. Ordinary Forge is unchanged.
`forge-control-ready` uses the same `select_forge_packet_datasets` as the
actual CONTROL packet builder.

Happy CONTROL NEXT remains:

```
/hypothesis-forge CURRENT_REPRESENTATION_CONTROL
```

## Recurring commands (post-merge, not this atom)

VPS: `list-live-cohorts` → `build-live-source` → `seal-live-cohort` →
`verify-live`. Copy sealed tree. Local: `verify-live` → `import-live` →
`forge-control-ready`. Exact fences:
`docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`.

## Residual UNKNOWN

Only runtime facts that need the next live acceptance after merge+deploy:

- live Factory still has the exact C1 members/dues/publication state as at
  last readback;
- live RDP MEMBER_BATCH bytes still carry the copied discovery admission clock;
- first live transport/import on the real split-host pair.

No remaining software question this atom was supposed to answer.

## Post-merge resume

Deploy exact merged SHA to Factory and repeat cohort-1 acceptance from
list-live-cohorts → source → seal → verify → split-host transfer →
local import → forge-control-ready. Do not run `/hypothesis-forge` in this
atom.

`CAPABILITY_RADAR_NOW=NONE`. STOP before merge. No deploy.
