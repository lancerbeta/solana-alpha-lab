# TASK-27 Stage B exact owner packet contract v1

## Purpose

`T27-A1S1_STAGE_B_EXACT_OWNER_PACKET_OFFLINE_V1` prepares the smallest
offline packet for a possible Stage B historical-read decision. It binds the
Stage A retained pool identity to two future Solana Tracker GET candidates and
reuses the already owner-nominated A7 anchor as a proposed, frozen 24-hour
UTC window.

The packet performs no provider/API/RPC/WSS action, does not read a
credential, and retains no new raw provider response. It is not an approval,
not a request, and not a historical-data result.

## Frozen proposed target

The only proposed target is the Stage A identity:

- network: `solana`;
- pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`;
- quote mint: wrapped SOL; and
- DEX: `pumpswap`.

The proposed window is inherited from A7's owner-nominated
`before_timestamp=1786186800`:

```text
[1786100400, 1786186800) UTC
2026-08-07T11:00:00Z through 2026-08-08T11:00:00Z
96 natural 900-second intervals
```

This reuse prevents a floating latest-window request. It remains
`PENDING_NEW_STAGE_B_OWNER_AUTHORITY`; the prior A7 permission does not carry
over to Solana Tracker.

## Future request shape

Only a new exact owner instruction may permit the two candidate GETs:

1. one token-identity read for the frozen base mint; and
2. one pool-specific chart read for the same base mint and frozen pool.

The chart must use `type=15m`, the exact UTC epoch bounds above,
`currency=usd`, `removeOutliers=false`, and `fastCache=false`. The local
credential may be supplied only through a redacted local header transport. Its
name and value must not appear in a URL, fixture, contract, receipt, log or
chat.

The future runtime must retain the exact raw responses outside Git under the
existing Task-27 retention rule. It must stop, with no retry or fallback, on a
credential, quota, wire-shape, identity, alignment, gap, duplicate, volume or
hash-reconciliation failure. Helius reconstruction, a token-only chart,
dynamic pool selection and automatic provider fallback are forbidden.

## Non-claims

This offline packet has no historical observations. It cannot claim data
availability, PIT admissibility, alpha, strategy, quote, execution, PnL,
NetReturn, cashflow or TASK-27 acceptance. Its sole outcome is
`OWNER_EXTERNAL_AUTHORITY_REQUIRED`.

## Owner boundary

The next action requires a separate exact owner approval that names these two
request IDs, preserves the zero-spend cap and explicitly allows local-header
credential use. A successful request would still only decide whether this one
24-hour panel is suitable for bounded history feasibility; it cannot approve
broader capture or trading.
