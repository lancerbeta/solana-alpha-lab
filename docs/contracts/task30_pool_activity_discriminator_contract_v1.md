# TASK-30 — Pool activity discriminator contract v1

## Identity

- task: `TASK-30`
- atom: `T30-A16_ONE_BOUNDED_POOL_ACTIVITY_DISCRIMINATOR_V1`
- contract: `TASK30-POOL-ACTIVITY-DISCRIMINATOR-V1`
- consumer: `RC001-H07-H01-LIQUIDITY-RETENTION`
- target: Solana pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- upstream evidence: `T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001`

## Estimand

Did at least one direct pool-address signature occur strictly after the A15P
subscription acknowledgement second and before the capture terminal second?
This is a route diagnostic, not proof of a WSS defect, market-data observation
or strategy trial.

## Frozen request proposal

One future Helius Standard RPC `getSignaturesForAddress` request with
`commitment=confirmed`, `limit=1000`, no pagination, retry, fallback or
transaction follow-up. Current authority remains zero. A future call requires
the exact phrase stored in the policy.

## Time and page semantics

The exact capture is
`[2026-08-12T09:27:52.749910Z, 2026-08-12T09:37:53.059095Z]`, and the
subscription acknowledgement is `2026-08-12T09:27:53.436278Z`.
Whole-second `blockTime` proves post-ack activity only for
`1786526873 < blockTime < 1786527473`.

No post-ack activity is supported only when the oldest record of a valid
newest-first page is strictly earlier than the acknowledgement-floor second.
An empty or short non-bracketing page does not prove provider completeness and
stays `HISTORY_COVERAGE_UNKNOWN`.

Boundary seconds, null time, a full page that does not reach the
acknowledgement, short or empty non-bracketing history, schema drift, ordering
drift and RPC error stay typed UNKNOWN.

## Truth precedence

All records must have the frozen shape, a recognized frozen Solana
`TransactionError|null` variant accepted by the repository-pinned `solders`
parser, unique signatures and non-increasing slots; records sharing a slot must
agree on `blockTime`. After structural validity is established, one strict
post-ack record is sufficient positive evidence even if other valid records
have null or boundary time. Positive evidence does not prove a trade or a WSS
delivery failure.

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
