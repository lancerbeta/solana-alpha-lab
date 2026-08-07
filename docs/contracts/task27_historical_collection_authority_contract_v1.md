# TASK-27 — Historical collection authority contract v1

## Purpose

This offline contract defines the smallest authority and evidence packet for a
future historical Solana pool price/volume feasibility capture.  It does not
collect data and does not authorize a provider request.

Its only possible owner-level outcomes are `AUTHORIZE_FEASIBILITY_CAPTURE`,
`REDESIGN`, and `CLOSE_DATA_ROUTE`.  `AUTHORIZE_FEASIBILITY_CAPTURE` is a
recommendation for a separate owner gate, not authority to make any request.

## Evidence grades

- `DESCRIPTIVE_ONLY` means history obtained later can describe an earlier
  path, but cannot establish when the observations were known.
- `PIT_ADMISSIBLE` requires an explicit source-backed availability proof for
  the decision-relevant observations.  A timestamp, retrieval time, or
  complete historical panel alone is not such proof.

Missing availability proof is unknown.  It cannot be substituted with event
time, current fetch time, or an inferred statement that the information was
available at a past entry point.

## Future feasibility proposal

The only candidate source name in v1 is
`GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`.  It remains a candidate: it
creates neither standing access nor a fallback-provider right.

A later separate authority packet must freeze the discovery/selection snapshot
and may propose no more than:

- 6 discovery requests;
- 24 OHLCV requests;
- 15-minute intervals;
- 24 consecutive hours per panel;
- 12 complete retained panels.

Discovery demonstrates only a source surface.  It is not a market universe,
representative sample, watchlist, alpha signal, or execution route.  Each
selected panel must retain a stable selection-snapshot ID and SHA-256, its
selection time, and an evidence/raw manifest ID.

Fewer than 12 complete panels, an ambiguous identity, a coverage gap, a
missing selection snapshot, missing raw evidence, or source incompatibility
requires `REDESIGN` or `CLOSE_DATA_ROUTE`.  No rule may be relaxed silently.

## Retention

- Keep raw evidence from a failed or unusable feasibility probe for 30 days
  with its failure receipt, except where a stronger legal or security rule
  applies.
- Keep raw evidence behind an accepted dataset, trial, or owner decision with
  that dependent research and its hashes.  It does not expire merely because
  30 days pass.

## Authority and non-claims

This v1 contract makes zero provider/API/RPC/WSS calls and retains zero raw
provider responses.  It grants no credential, R2/R3, wallet, signer,
transaction, cash, Catalog/registry, Project Source, strategy, or execution
authority.

It cannot establish alpha, a trade, quote, fill, route, PnL, NetReturn, or
owner cashflow.  A historical price/volume feasibility decision is not an
execution or profitability decision.

## Acceptance boundary

Acceptance requires deterministic synthetic schema and adversarial tests.
The tests must reject an unsupported PIT claim, a cap breach, insufficient
panels, an unfrozen selection, provider fallback, missing raw evidence, and a
claim scope beyond historical feasibility.
