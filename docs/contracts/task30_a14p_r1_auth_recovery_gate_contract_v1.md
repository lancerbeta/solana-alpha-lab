# TASK-30 A14P-R1 — auth-recovery gate contract v1

## Purpose

Record one bounded, versioned recovery path after the first A14P foreground
attempt ended immediately as `CONNECTION_OR_AUTH_REJECTED` with zero provider
credits and no returned capture. R1 is a new offline gate; it is not a retry,
fallback or provider-selection decision.

## Frozen recovery boundary

- target, pool filter and Helius `transactionSubscribe` wire remain identical
  to A14P V1;
- one foreground connection and one subscription only;
- effective runtime cap: 540 seconds, 500 notifications, 1,000,000 stream
  bytes and 100,000 bytes per frame;
- no retry, reconnect, fallback, scheduler, second provider or background
  process;
- V2 uses `local/task30_forward_stream_v2`, leaving the V1 receipt immutable;
- the V2 owner phrase is distinct and is not authority until separately
  supplied by the owner on merged exact-main bytes.

## Prior evidence and recovery rule

The prior V1 receipt is referenced by run id
`20260811T221947Z-ec16b97f` and terminal state
`CONNECTION_OR_AUTH_REJECTED`. Its sanitized receipt hashes remain outside
Git under the A4 ignored local root. It contains no provider raw manifest,
zero notifications, zero estimated credits and no evidence of a started WSS
exchange. R1 may not rewrite, delete or reinterpret it.

The new V2 profile is admissible only after offline validation, delivery and
exact-main CI. A future external call still requires the exact V2 phrase and
must stop after one terminal receipt. A missing or invalid terminal remains
unresolved; `UNKNOWN` is never zero, empty or settled.

## Non-claims

This contract does not claim provider suitability, data availability, interval
coverage, empty intervals, zero volume, PIT admissibility, alpha, strategy,
execution, inventory, settlement, PnL, NetReturn, trial status or TASK-30
acceptance. It grants no credential, provider, wallet, transaction, cash or
Project Sources authority.

## DoD

1. V1 and V2 profiles are closed and type-strict in code, schema and fixtures.
2. V2 has a separate logical root and exact owner phrase; V1 phrase is rejected.
3. Deterministic tests prove V2 preflight, fake capture, one-shot retention and
   no V1-root reuse.
4. Prior V1 negative evidence is bound by hash/run id without raw bytes in Git.
5. Catalog/generated views, targeted validation and one tracked-only delivery
   gate pass.

`STATE_CHANGE=NONE` until a later owner-authorised V2 external gate produces a
valid receipt.
