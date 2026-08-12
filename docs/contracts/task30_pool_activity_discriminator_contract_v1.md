# TASK-30 — Pool activity discriminator contract v1

## Identity

- task: `TASK-30`
- atom: `T30-A16_ONE_BOUNDED_POOL_ACTIVITY_DISCRIMINATOR_V1`
- contract: `TASK30-POOL-ACTIVITY-DISCRIMINATOR-V1`
- consumer: `RC001-H07-H01-LIQUIDITY-RETENTION`
- target: Solana pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- upstream evidence: `T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001`

## Estimand

Did at least one direct pool-address signature occur strictly inside the exact
A15P WSS capture interval? This is a route diagnostic, not a market-data or
strategy trial.

## Frozen request proposal

One future Helius Standard RPC `getSignaturesForAddress` request with
`commitment=confirmed`, `limit=1000`, no pagination, retry, fallback or
transaction follow-up. Current authority remains zero. A future call requires
the exact phrase stored in the policy.

## Time and page semantics

The exact interval is
`[2026-08-12T09:27:52.749910Z, 2026-08-12T09:37:53.059095Z]`.
Whole-second `blockTime` proves interior activity only for
`1786526872 < blockTime < 1786527473`.

No interior activity is supported only when a valid newest-first page either:

1. contains fewer than 1000 records and therefore exhausts the available
   address history; or
2. contains 1000 records and its oldest record is strictly earlier than the
   start-floor second.

Boundary seconds, null time, a full page that does not reach the start, schema
drift, ordering drift and RPC error stay typed UNKNOWN.

## Truth precedence

All records must have the frozen shape and unique signatures. Non-null times
must be newest-first. After structural validity is established, one strictly
interior record is sufficient positive evidence even if other valid records
have null or boundary time. Positive evidence does not prove a trade.

## Authority

Offline work permits no provider/API/RPC/WSS call, credential read, raw external
write, cash spend, wallet/signer/transaction action, TASK-30 trial or acceptance.

## Explicit non-claims

The contract does not infer PumpSwap trade identity, direction, price, volume,
candle completeness, zero activity, PIT admissibility, provider-wide
reliability, alpha, strategy, execution, PnL or numeric NetReturn.

## Decision enum

- `OFFLINE_DISCRIMINATOR_READY_FOR_OWNER_GATE`
- `REDESIGN_DISCRIMINATOR`
- `PAUSE`
- `CLOSE_ROUTE`

Readiness does not grant external authority.
