# TASK-27 bounded public-history feasibility authority contract v1

## Purpose

`T27-A0-A4_BOUNDED_PUBLIC_HISTORY_FEASIBILITY_AUTHORITY_PACKET_V1` freezes the
smallest offline packet that may prepare a later owner review of one bounded
public historical pool price/volume feasibility capture. It does not collect
data, contact a provider or grant a provider request.

The packet answers only whether a later exact owner external-read request can
be formulated. It does not establish source fitness, PIT-admissible history,
alpha, execution, PnL, NetReturn or owner cashflow.

## Decision states

Exactly one outcome is permitted:

- `READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW`;
- `REDESIGN`; or
- `CLOSE_DATA_ROUTE`.

`READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW` means that an otherwise complete
synthetic packet is ready for a separate owner review. It never grants a
provider read: `provider_read_authority=false` remains mandatory.

## Required future proposal

The sole source candidate is `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`.
There is no fallback-provider right. A future proposal must retain one frozen
selection-snapshot ID and SHA-256, selection time, universe description and
raw-evidence manifest identity.

The future capture can propose at most six discovery reads and 24 OHLCV reads.
Each panel is 24 consecutive hours of 15-minute intervals, and at least 12
complete retained panels are required. An ambiguous identity, incomplete
panel, missing snapshot/hash, missing raw manifest or cap breach requires
`REDESIGN` or `CLOSE_DATA_ROUTE`; no threshold may be relaxed silently.

## Source and evidence truth

`ACTIVATION_CONFIRMED_USER_SMOKE` requires an exact seven-role Source-smoke
reference. Any other state is `SOURCE_ALIGNMENT_REQUIRED` and cannot emit
`READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW`.

History is `DESCRIPTIVE_ONLY` unless a source-backed availability proof exists.
`PIT_ADMISSIBLE` without that proof is invalid. Retrieval time, event time and
panel completeness cannot substitute for availability proof.

Failed or unusable future raw evidence is retained for 30 days with its
failure receipt. Decision-supporting evidence is retained with its dependent
research and hashes.

## Authority and non-claims

This atom makes zero provider/API/RPC/WSS calls, uses no credential, opens no
R2/R3 value or path, retains no provider response, changes no Project Source
or Catalog record, creates no wallet/signer/transaction and spends no cash.

It establishes no signal, market universe, representative sample, route,
quote, fill, inventory, realized result, PnL, NetReturn, owner cashflow,
strategy promotion or external authorization. A later external read requires
a new exact owner instruction naming the actual bounded request.
