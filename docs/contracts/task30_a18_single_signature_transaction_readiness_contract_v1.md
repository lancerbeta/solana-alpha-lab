# TASK-30 A18 — Single-signature transaction readiness contract v1

## Purpose

This atom answers one cheap question after A17 produced a real signature:
can one read-only `getTransaction` response be safely bound to the selected
Orca POPCAT/WSOL pool and yield conservative token-balance deltas?

It does not claim that the observed transaction is ours, that it is an Orca
swap, or that a price, volume, fill, PnL, alpha or NetReturn exists.

## Outcome and boundary

- Named consumer: `RC001-H07-H01-LIQUIDITY-RETENTION`.
- Cheapest falsifier: one exact signature read; null, schema drift or ambiguity
  is retained as an explicit terminal state.
- External budget: one standard Solana RPC POST, at most 2,000,000 bytes,
  no retry/fallback/reconnect, raw bytes outside Git under A4.
- Current implementation is offline and has zero provider authority.
- Future owner gate phrase is frozen in the policy config; it requests one
  keyless standard-RPC read and does not grant trial, acceptance or cash authority.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` because this crosses an on-chain
  response contract and can influence financial interpretation.

## Truth rules

The pool address and signature must both be present. Token balances are keyed by
`accountIndex + mint`; duplicate or missing rows are ambiguous, never zero.
Only a coherent opposite-direction base/quote delta pair becomes
`TRADE_DATA_CANDIDATE`. That label means “candidate balance evidence”, not a
trade, price, volume, fill, owner action or outcome.

Terminal states are `TRADE_DATA_CANDIDATE`,
`TRANSACTION_PRESENT_NO_TRADE_PROJECTION`, `TRANSACTION_NULL_OR_UNAVAILABLE`,
`PROVIDER_TYPED_FAILURE` and `TRANSPORT_OR_COVERAGE_UNKNOWN`. Every terminal
keeps price, volume, numeric NetReturn, alpha and TASK-30 trial/acceptance false.

## Reuse-first decision

`REUSE_DECISION=WRAP`: reuse the existing standard JSON-RPC request shape,
bounded HTTP capture and A4 retention boundary. `BUILD` is limited to the
Orca-neutral, pool-bound balance-delta classifier. The historical TASK-09
getTransaction response is evidence that the standard RPC shape was reached,
but its additive `transactionIndex` drift is preserved; it is not silently
promoted to a universal schema guarantee.

The provider-route registry is append-only: v3 preserves v2’s exact SHA and
route semantic hashes, then records the historical standard-RPC route as
`SOLANA-STANDARD-GET-TRANSACTION-001`. This is not a Helius route; a future
Helius-specific route remains a registry gap until separately observed.

## Replan and product horizon

This is one terminal atom. No A18R suffix is automatic. A null, ambiguous or
schema-drift result goes to exactly one owner-level choice: `PIVOT`,
`ACCEPT_UNKNOWN`, `DEFER` or `CLOSE`.

NOW: run one exact external read only after the owner gate; value is knowing
whether the existing active-pool signature has usable raw balance evidence.
WATCH: an Orca instruction/event decoder only if the result is target-bound and
the named consumer still needs it. No decoder is justified before that.

`FACTORY_FIT_REVIEW=FULL_REVIEW`; `PROJECT_SOURCES_DISPOSITION=NO_CHANGE`;
`STATE_CHANGE=NONE`.
