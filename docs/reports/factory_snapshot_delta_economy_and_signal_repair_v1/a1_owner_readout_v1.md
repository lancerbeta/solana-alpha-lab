# Owner readout — FACTORY_SNAPSHOT_DELTA_ECONOMY_AND_SIGNAL_REPAIR_V1

## Terminal

New SNAPSHOT_PLUS_DELTA writes persist schema `2.0` without `unchanged[]`.
Replay verifies chain identity and hashes the target snapshot once. Watch maps
`DATA_STALE` only to `SOURCE_DATA_STALE`. Live 24h storage growth is scaled by
the actual observation span. This PR does not deploy, rewrite historical fat
deltas, compact SQLite, or change watch cadence.

## Entry / outcome

- `DECISION_DELTA`: compact delta encoding + fast exact replay + one freshness
  incident + span-normalized 24h growth. Lease stays 120s.
- `UNCERTAINTY_REMOVED`: persisted delta bytes scale with the changed set, not
  the member universe; mixed v1 fat → v2 compact reconstructs; one DATA_STALE
  is not also COLLECTOR_STALLED; a ~31h byte delta is not treated as 24h.
- `CAPABILITY_OR_EVIDENCE`: focused tests plus existing HOT90 reconstruct/
  hydrate path; semantic discovery through `SEM-REMOTE-OPS-RECOVERY` and
  `SEM-LIVE-COLLECTION`.
- `STOP`: merge gate. No VPS mutation from this handoff.
- `NEXT`: later OPERATE commissioning in
  `docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md`. Not another Git
  development task.

`SPEC_ROUTE`: `NONE`
`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `ROUTINE_NO_SWITCH`

## Planes

| Plane | Owns |
|---|---|
| Git | compact delta writer/reader, watch mapping, growth math, Catalog |
| VPS runtime | live HOT90 stage, current fat residues, tick wall-time |
| Drive | already-verified archives; this PR does not rewrite them |
