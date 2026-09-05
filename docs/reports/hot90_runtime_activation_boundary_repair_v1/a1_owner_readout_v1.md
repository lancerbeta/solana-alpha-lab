# Owner readout — HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1

## Terminal

Git HOT90 YAML is policy / safe default `CURRENT_SAFE`, not live Factory stage.
Current host activation is preserved local runtime state. Ordinary stage
transitions do not need another Git PR. This PR does not deploy or mutate the
VPS.

## Entry / outcome

- `DECISION_DELTA`: tracked `configs/factory_hot90_archive_activation_v1.yaml`
  returns to `CURRENT_SAFE` as the safe default when no valid runtime file
  exists. Host stage lives at `local/factory_v1/hot90_activation_runtime.yaml`.
- `UNCERTAINTY_REMOVED`: a Git diff is no longer required to move
  `CURRENT_SAFE → WRITE_ONLY_SHADOW → DURABILITY_CUTOVER → RETENTION_ACTIVE`
  when policy/implementation are unchanged.
- `CAPABILITY_OR_EVIDENCE`: loader precedence (valid runtime / absent Git
  default / invalid fail-closed); `scripts/hot90_activation.py show|set`;
  tests for SNAPPY default, WRITE_ONLY_SHADOW ZSTD, Drive/mutable-backup
  cutover, RETENTION_ACTIVE without implied eviction, malformed/symlink/invalid
  combinations, and no second production source of truth.
- `STOP`: merge gate of this repair PR. No VPS mutation from this handoff.
- `NEXT`: OPERATE continuity migration — write validated runtime
  `WRITE_ONLY_SHADOW` (Drive/compaction/eviction false) before deploying the
  merged SHA, then prove no stage transition. Not another Git stage PR.

`SPEC_ROUTE`: `NONE`
`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `ROUTINE_NO_SWITCH`

## Ownership after this repair

| Plane | Path | Owns |
|---|---|---|
| Git | `configs/factory_hot90_archive_activation_v1.yaml` | allowed stages, validation, `CURRENT_SAFE` safe default |
| Host | `local/factory_v1/hot90_activation_runtime.yaml` | current stage and Drive/compaction/eviction flags |
| Readback | `scripts/hot90_activation.py show` | actual loader result |

`SET` is an operational mutation. The CLI grants no authority. Production
stage, Drive writes and destructive flags still need an exact owner gate.

## Continuity (after merge, not this PR)

1. Before deploy: write runtime `WRITE_ONLY_SHADOW` with all flags false.
2. Deploy exact merged SHA (`local/` preserved).
3. `show` must read `WRITE_ONLY_SHADOW` from `activation_source=RUNTIME`.

## Confirm

- Drive enabled remains a runtime flag, default false
- compaction remains a runtime flag, default false
- eviction remains a runtime flag, default false
- `RETENTION_ACTIVE` does not imply eviction
