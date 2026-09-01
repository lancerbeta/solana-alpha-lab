# OBSERVATION_RUNTIME_DEPLOY_SHA_REPAIR_V1 — owner readout

## What changed

ObservationSchedule producer identity on sanctioned exact-SHA no-`.git`
Factory roots now resolves via:

1. explicit valid `producer_git_sha` (runtime config)
2. root-local Git HEAD (`.git` present at deploy root)
3. `.factory_deploy_sha` (40 lowercase hex; regular file; fail closed)

The deploy pin is **identity only** — it does not authorize ticks, provider
calls, or campaign activation.

## Proof

- Unit/vertical suite: `tests/test_observation_runtime_deploy_sha_repair.py`
- Synthetic VPS layout (no `.git` + `.factory_deploy_sha`) no-live `tick --once`
  reaches `TICK_REFUSED_NO_LIVE_DEFAULT` with `provider_calls=0`,
  `credential_reads=0` (not `PRODUCER_GIT_SHA_UNAVAILABLE`)

## Operator navigation

- Host locator: `docs/operator/FACTORY_REMOTE_HOST.md`
- Collector protocol: `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`
- Cursor alwaysApply rule points to both before collector/campaign actions

## Explicit next operation (not this atom)

Deploy repaired exact `main` → no-live tick smoke → timer enable/readback →
rerun campaign readiness classification.

Named future consumer (not implemented here): `DAILY_COLLECTOR_OWNER_PULSE`.

## Residual risk (accepted)

Pin ≠ tree bytes can still mislabel provenance if deploy mid-failure leaves a
stale pin. Identity can lie; it still does not grant authority.

## Non-claims

No VPS mutation/deploy, no provider/API/RPC/WSS, no credential values, no
campaign authorize/activate, no spend, no wallet/signer/tx, no alpha,
no `OPERATIONAL_READY`, no daily pulse implementation.
