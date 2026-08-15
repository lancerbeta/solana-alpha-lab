# TASK-30 A26 H07/H01 owner-fork packet contract v1

## Decision

Decide only whether a one-shot ~`$5` Helius purchase can falsify the frozen
`RC001-H07-H01-LIQUIDITY-RETENTION` estimand. If it cannot, encode the exact
owner fork and stop. This atom does not spend, capture, retire the hypothesis,
or freeze notional buckets.

## Frozen inputs

The packet reads, never restates:

- A25 acceptance
  `docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json`
  with SHA-256
  `c29ecd424e4c2276259ffc05aec6fb8058b53469a30c763db972c0581f84ceca`.
  Terminal must remain
  `ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN`.
- Current registry `configs/provider_route_capability_registry_v6.yaml`
  (`PROVIDER-ROUTE-CAPABILITY-REGISTRY-006`), validated by the existing v6
  module. An absent `ROUTE_FEASIBILITY` route is `REGISTRY_GAP`, not authority
  to buy or to insert a row.
- Immutable predecessor `configs/provider_route_capability_registry_v1.yaml`.
- RC001 freeze `configs/task28_rc001_registry_freeze_v1.yaml` for
  `NOTIONAL_BUCKET_SET_V1`.
- Reuse record `REUSE-T04-JUPITER-V2-001`: `WRAP` /
  `ACCEPT_CONTRACT_RUNTIME_DEFERRED`. That is not a live quote route.

Any hash, terminal, cluster-count or registry-set drift is
`STOP_INTEGRITY_CONFLICT`.

## What `$5` Helius cannot buy

Helius registered operations are trade/log history:
`GET_SIGNATURES_FOR_ADDRESS`, `LOGS_SUBSCRIBE_MENTIONS`,
`GET_TRANSACTIONS_FOR_ADDRESS_FULL`. They cannot supply the 13 frozen
`ROUTE_FEASIBILITY` fields. A23 already completed the one pool-day raw batch.
A second Helius page does not create a second `POOL_DAY` cluster and does not
create quotes.

A25 requires ≥4 `POOL_DAY` clusters even for
`VARIANCE_CALIBRATION_PILOT_NOT_HYPOTHESIS_TEST`. Quote evaluations per cluster
are `96 × |NOTIONAL_BUCKET_SET_V1|`. The bucket set is
`FROZEN_PARAMETER_DEFINITION_ABSENT`; TASK-21 `$10/$25/$50/$100` must not be
adopted. Therefore the quote-call budget is undefined. An illustrative
`4 × 96 × 1 = 384` figure may be printed only as
`ILLUSTRATIVE_N1_NOT_A_FROZEN_PARAMETER`.

No Jupiter quote `route_id` exists in registry v1 through v6. That is
`REGISTRY_GAP`. The gap is not provider failure and grants no call.

## Terminal outcomes

- `FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY` — unpaid proof stands;
  owner must later choose one fork phrase; TASK-30 stays `BLOCKED_DATA`.
- `STOP_INTEGRITY_CONFLICT` — frozen input drifted.

## Non-claims

No TASK-30 acceptance, RC001 promotion, H07/H01 trial, effect estimate, alpha,
fill, settlement, PnL, NetReturn, cashflow, prospective PIT route, or
continuous price. Missing remains unknown. Subscriptions stay premature.
The owner pays any future crypto themselves; this atom never handles wallet,
seed, signer, card or transfer.
