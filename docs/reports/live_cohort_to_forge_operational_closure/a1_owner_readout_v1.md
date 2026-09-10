# LIVE_COHORT_TO_FORGE_OPERATIONAL_CLOSURE_V1 — owner readout

## What closed

Weekly publication of a **mature** live cohort is now one operator path, not a Git atom.

Planes stay: VPS Observation RDP → sealed verified release → verified transport → local `data_plane` LIVE CORPUS. Forge never imports a moving Observation RDP.

Happy terminals: `LIVE_COHORT_PUBLISHED_TO_FORGE` then `FORGE_CONTROL_READY`.

NEXT (do **not** run in this atom):

```
/hypothesis-forge CURRENT_REPRESENTATION_CONTROL
```

## Recurring commands

Same-host only when Forge `data_plane` is already on this filesystem. Omit `--cohort-id` to publish the next mature unimported cohort.

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py list-live-cohorts --observation-rdp local/factory_v1/observation_rdp --ops-store local/factory_v1/observation_schedule_state.sqlite --schedule-sha256 <64hex> --activation-id <ACT-...> --data-root local/factory_v1/data_plane
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py publish-live-cohort --observation-rdp local/factory_v1/observation_rdp --ops-store local/factory_v1/observation_schedule_state.sqlite --schedule-sha256 <64hex> --activation-id <ACT-...> --data-root local/factory_v1/data_plane
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py forge-control-ready --data-root local/factory_v1/data_plane
```

Production (Observation RDP on VPS, Forge local): `list-live-cohorts` + `build-live-source` + `seal-live-cohort` + `verify-live` on the VPS, copy the sealed tree, then `import-live` + `forge-control-ready` locally. Exact fences live in `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`. On VPS without Forge `--data-root`, `imported` is unknown — pick the mature `REL-...` that is not already in the local LIVE CORPUS.

## Source identity

Cohort-scoped snapshot: `live_observation_rebuild/cohort={cohort_id}/source_snapshot.json`.

Bind: `schedule_sha256` + `activation_id` + `cohort_id` + exact window. Register-time `OBSERVATION_SCHEDULE` may have `run_id=null`. Clocks are not identity.

Producers: `schedule_producer_git_sha` + sorted `contributing_producer_git_shas`. Singular `producer_git_sha` only when the set has exactly one SHA.

Closure: SQLite/runtime receipt. Missing/open C1 dues or publication fail closed. Cohort-2 future PENDING does not block cohort 1.

Coverage: worst class, `GAP_SUSPECTED` ≠ `GAP_CONFIRMED`. `READY_VALID_WITH_COVERAGE_LIMITATION` is sealable.

## Defects closed in this atom

- `LIVE_SOURCE_SCHEDULE_MISSING` on register-before-activation
- rolling multi-producer treated as a conflict / latest SHA
- default-False READY without closure evidence
- C2 activity rewriting C1 source
- empty C-pure observation allow-list matching all panels
- `LOW_YIELD` counted typed_missing toward CONTROL
- CLI happy path / next-mature list / `TRANSPORT_HASH_MISMATCH`
- Factory `build-live-source` bypassing completeness gates

## Residual UNKNOWN

- CONTROL-first is operator NEXT, not an HFIC hard-block of ordinary Forge
- in-place mutation of a historical member parquet (RDP is append-only)
- HFIC context packet `MAX_DATASETS=8` can still omit the live corpus from Prompt A context even if `forge-control-ready` passes
- live cohort 1 seal/import is **post-merge** (this atom did not touch the VPS)

## Post-merge live acceptance

After merge + Factory deploy of this head: run the VPS seal/copy/local import path for cohort 1 (`REL-20260902T111900Z-20260909T111900Z`, activation `ACT-619AE64E885E995E`) and require `FORGE_CONTROL_READY`. No Git/PR on that happy path.

## Reviews

Isolated: CODE_REVIEWER PASS, GOAL_DOD_CRITIC PASS, ARCHITECTURE_CRITIC PASS (`packet_fingerprint_sha256=ca48463123d96befbf7b9686790ae1d0ec35f64714069c4e11c42210da47300c`). Owner-UX: list CLI exists; VPS cannot see local Forge imports without `--data-root`.

`CAPABILITY_RADAR_NOW=NONE`. STOP before merge. No deploy.
