# TASK-30 A16 — One bounded pool-activity discriminator design

**Date:** 2026-08-12
**Status:** APPROVED_BY_OWNER_START
**Entry Gate:** `START_AS_WRITTEN`

## Problem

The A15P Helius Standard WSS `logsSubscribe` route was accepted but produced no
notifications during the frozen interval
`[2026-08-12T09:27:52.749910Z, 2026-08-12T09:37:53.059095Z]`. That result is
`NO_OBSERVATION_UNKNOWN`: it does not distinguish an inactive pool from a WSS
delivery gap.

## Decision to improve

Decide whether the next useful work is:

- repair or replace the WSS observation route because direct pool-address
  activity existed in the capture window; or
- stop blaming WSS for this window because no direct pool-address activity is
  supported by a complete/bracketing signature page.

The consumer is `RC001-H07-H01-LIQUIDITY-RETENTION`. The cheapest falsifier is
one future Helius Standard RPC `getSignaturesForAddress` request for the exact
pool. The offline A16 atom creates no provider authority.

## Reuse decision

`WRAP`: use the standard Solana JSON-RPC method and the project's existing
Helius secret-safe transport/retention conventions. Do not build a history
collector, scheduler, generic RPC platform or transaction decoder.

Official method facts frozen as of 2026-08-12:

- results are returned newest first;
- `limit` is bounded to 1–1000;
- `blockTime` may be null;
- `confirmed` or `finalized` commitment is supported.

Sources:

- https://solana.com/docs/rpc/http/getsignaturesforaddress
- https://www.helius.dev/docs/rpc/guides/getsignaturesforaddress

## Exact future request proposal

```json
{
  "jsonrpc": "2.0",
  "id": "task30-a16-pool-activity-discriminator",
  "method": "getSignaturesForAddress",
  "params": [
    "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
    {"commitment": "confirmed", "limit": 1000}
  ]
}
```

Future runtime is limited to one request, one credential read, one A4 raw write,
one estimated provider credit, no retry, no fallback and no transaction
follow-up. It requires a separate exact owner gate.

## Frozen interval and conservative time rule

- exact start: `2026-08-12T09:27:52.749910Z`
- exact terminal: `2026-08-12T09:37:53.059095Z`
- integer start floor: `1786526872`
- integer terminal floor: `1786527473`

Because provider `blockTime` has only whole-second precision, a record proves
interior activity only when `blockTime > 1786526872` and
`blockTime < 1786527473`. A record on either boundary second is ambiguous.

## Closed decision states

- `POOL_ACTIVITY_OBSERVED_WSS_DELIVERY_GAP`: at least one valid signature record
  is strictly inside the frozen interval.
- `NO_DIRECT_POOL_ACTIVITY_SUPPORTED`: no interior record exists and the result
  page either exhausts history or reaches strictly before the interval start.
- `BOUNDARY_TIME_AMBIGUOUS_UNKNOWN`: only relevant evidence is on a boundary
  second.
- `NULL_BLOCK_TIME_UNKNOWN`: no interior proof exists and a relevant record has
  null time.
- `PAGE_TRUNCATED_UNKNOWN`: a full 1000-record page does not reach before the
  interval start.
- `ORDERING_OR_SCHEMA_DRIFT_UNKNOWN`: ordering, duplicates or record shape
  violate the frozen contract.
- `MALFORMED_OR_RPC_ERROR_UNKNOWN`: JSON-RPC error or malformed envelope.

Positive proof wins over unrelated null or boundary records because one valid
interior signature is sufficient to falsify pool inactivity. Every negative
decision remains explicitly scoped to direct address activity in this one
window.

## Non-claims

A16 does not claim a PumpSwap trade, buy/sell direction, price, volume, empty or
complete candle, PIT panel, provider-wide reliability, alpha, strategy,
execution, PnL or NetReturn. Missing, null and ambiguous evidence never becomes
zero or inactivity.

## Product Horizon Radar

**NOW — A16 exact discriminator.** Value: prevent another blind WSS wait and
select the next route using one decision-changing observation. Cost/risk: one
future credit and one bounded raw object after owner gate. Owner:
`LOCAL_WORK_CODEX_AFTER_EXACT_GATE`. Trigger: offline packet passes delivery.

**WATCH — bounded transaction follow-up.** Value: establish whether an observed
pool-address signature is an actual PumpSwap trade. Cost/risk: additional RPC,
decoder and truth-contract scope. Owner: goal owner. Trigger: A16 first proves
interior address activity and the distinction changes the H07/H01 experiment.

## Delivery boundary

This atom ends after offline contract, deterministic tests, Catalog bindings,
FULL Factory Fit, PR and CI. It must stop before credential access, provider
call, raw external data write or TASK-30 acceptance.
