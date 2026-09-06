# Owner readout — FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1

## Terminal

Git now has one unattended-operability capability: closed-day archive → Drive →
exact SHA, local incident/recovery, UTC daily pulse, and an unconfigured-safe
heartbeat hook. Git still does not own live HOT90 stage, disk, Telegram, or
VPS liveness. This PR does not deploy, enable units, write Drive, or send
Telegram.

## Entry / outcome

- `DECISION_DELTA`: recurring consumers over existing
  `package_closed_day_archive` / `verify_remote_content_sha256`; one
  operability watch; explicit UTC `06:15 UTC` daily pulse; provider-neutral
  heartbeat URL env.
- `UNCERTAINTY_REMOVED`: upload/mtime/size cannot look durable; a 7-day
  outage can catch up oldest-first without a Git PR; incidents fire once;
  HASH_MISMATCH does not overwrite the same remote object; archive catch-up
  uses a wall/monotonic 900s budget; watch `--mode dry-run` does not persist
  incident JSON; HASH_MISMATCH days stay visible but do not consume the
  3-day catch-up slots.
- `CAPABILITY_OR_EVIDENCE`: four vertical loops + semantic route
  `SEM-REMOTE-OPS-RECOVERY` rebound to
  `CONFIG-FACTORY-REMOTE-OPERATIONS-V1-1-001` +
  `docs/operator/FACTORY_UNATTENDED_OPERABILITY.md`.
- `STOP`: merge gate. No VPS mutation from this handoff.
- `NEXT`: later OPERATE commissioning of new units after fresh live SHA
  readback. Not another Git development task.

`SPEC_ROUTE`: `NONE`
`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `ROUTINE_NO_SWITCH`

## Planes

| Plane | Owns |
|---|---|
| Git | capability, policy, units templates, Catalog, tests |
| VPS runtime | HOT90 stage, receipts, timers, incident state |
| Drive | mutable backup objects vs immutable closed-day archives |
| External watcher | future host-unreachable (not activated) |
