# FACTORY_LAUNCHPAD_POPULATION_CONTRACT_REPAIR — owner readout

## Pause proof

- Broken activation `ACT-490C21B69A1F8F8F` on schedule `490c21b6…` paused with terminal `PAUSED`.
- `ACTIVE_COUNT=0`; provider calls lifetime frozen at **34** across three 60s timer cycles.
- Timer remains enabled; paused semantics block provider calls.

## Root cause

Jupiter live `/tokens/v2/recent` rows carry `launchpad` (776/870 `pump.fun` in persisted
payloads). Authorized predicate used `FIELD-FIRST-POOL-SOURCE-001`, which reads
`firstPool.source` / `source` — both absent on live rows — yielding 618/618
`NOT_SELECTED_PREDICATE`.

## Repair

- New field `FIELD-LAUNCHPAD-001` → `row["launchpad"]` (typed TEXT, LIFECYCLE_TIMING family).
- Campaign preflight source predicate → `FIELD-LAUNCHPAD-001 EQ pump.fun`.
- Query profile parameter renamed to `launchpad_eq` (local population intent; no false server filter claim).
- `FIELD-FIRST-POOL-SOURCE-001` unchanged.

## MUST NOT RESUME

Schedule `490c21b69a1f8f8f878eb9d909f3fce62e3ffa9891c73d2e85ade9790949f7d8` is immutable
commissioning evidence. Replacement requires new `schedule_sha256`, register, authorize, activate.
