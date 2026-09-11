# LIVE_COHORT_MEMORY_BOUNDED_PUBLICATION_V1 — owner readout

## What closed

The proven C1 OOM (138844 members, ~61 min, kernel killed `python3`, SSH/tty
died) was a resource-safety failure of monolithic
`source_snapshot.json` plus N×census MEMBER_BATCH loads. This atom repairs the
pre-import publication path. Scientific semantics from #295 are unchanged.
This atom did **not** run live VPS source/seal/import.

Production source is now a small manifest plus parquet partitions:

`live_observation_rebuild/cohort=<cohort_id>/source_manifest.json`
`members.parquet`
`observations.parquet`

`build-live-source` / `publish-live-cohort` / `list-live-cohorts` /
`seal-live-cohort` / `verify-live` / `live-status` run in a child process.
Resource exhaustion is typed `SOURCE_BUILD_RESOURCE_LIMIT` /
`STOP_RETRY_BOUNDED_SOURCE_BUILD`. Retry the same bounded command; do not add
swap or resize the VPS. Collector/SSH/workbench should stay up.

## Memory bound (what the 150k stress proves)

C1-shaped stress: 150000 members, one observation identity per member, mixed
SNAPSHOT_PLUS_DELTA plus later C2. Helper MaxRSS was 170143744 bytes
(~162 MiB) versus a 1.25 GiB worker ceiling. SNAPSHOT_PLUS_DELTA history: 10 vs 100 identity
publications reconstruct the unit once (`reconstruct_calls=1`); extra
snapshots do not multiply full member-row scans. Reconstruct peak is the
reconstructed publication census, not a C1-filtered subset. This is not
proof that a mixed live snapshot much larger than C1, or a field-exploded
observation panel, stays under 1 GiB.

## Recurring operator path (post-merge only)

After deploy of the merged SHA and ordinary collector health:

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py list-live-cohorts --observation-rdp local/factory_v1/observation_rdp --ops-store local/factory_v1/observation_schedule_state.sqlite --schedule-sha256 <64hex> --activation-id ACT-619AE64E885E995E
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py build-live-source --observation-rdp local/factory_v1/observation_rdp --ops-store local/factory_v1/observation_schedule_state.sqlite --schedule-sha256 <64hex> --activation-id ACT-619AE64E885E995E --cohort-id REL-20260902T111900Z-20260909T111900Z --as-of <UTC>
```

Then readiness → seal → verify → split-host transfer → import →
`forge-control-ready`. Exact fences:
`docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`.

## Residual UNKNOWN

- Live C1 still ABSENT on Factory until post-merge deploy + bounded
  publication.
- 150k×1-obs RSS is the host-class C1-shaped bound, not an arbitrary panel
  explosion bound.
- `list-live-cohorts` still uses `not_after=now` for the observation horizon
  (same as #295).

`CAPABILITY_RADAR_NOW=NONE`. STOP before merge. No deploy in this atom.
