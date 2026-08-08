# TASK-27 exact single-pool selection and pilot-read packet v1

## Purpose

`T27-A0-A7_EXACT_SINGLE_POOL_SELECTION_AND_PILOT_READ_PACKET_V1` turns one
owner-nominated public pool page into a content-addressed offline packet for a
later exact owner decision. It specifies two future keyless public GET
requests but makes neither request, retains no provider response and grants no
provider-read authority.

The packet is the cheapest falsifier of pool identity, source shape, natural
15-minute continuity and raw-evidence retention. It does not establish source
fitness, point-in-time admissibility, alpha, execution, PnL, NetReturn or
owner cashflow.

## Owner-nominated selection

The sole technical feasibility target is:

- network: `solana`;
- pool address: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- owner-supplied URL:
  `https://www.geckoterminal.com/solana/pools/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- selection class: `OWNER_NOMINATED_SINGLE_POOL`; and
- universe description:
  `ONE_NON_REPRESENTATIVE_TECHNICAL_FEASIBILITY_TARGET`.

The canonical selection snapshot is hashed as sorted-key, minified UTF-8 JSON.
The page labels `PumpSwap` and `Cope/SOL` are only unverified hints. A later
metadata response must establish the actual DEX and base/quote identity; this
packet never infers them from the page label.

## Future exact pilot

The later pilot may make exactly two GET requests against the keyless public
GeckoTerminal API:

1. one metadata request for the exact Solana pool; and
2. one OHLCV request with 15-minute aggregation, `limit=96`, USD base-token
   values, `include_empty_intervals=false`, and frozen
   `before_timestamp=1786186800`.

The frozen boundary is aligned to the 900-second grid. A floating latest-window
request, a third request, automatic fallback provider, request-method change
or URL substitution is invalid.

## Evidence and decision rules

Future raw bodies are outside Git. The raw manifest must bind stable run and
request IDs, canonical URL, request/response timestamps, HTTP status, content
type, byte count, raw SHA-256, parser version, parsed-output hash, retention
class and a failure reason where applicable. A tracked receipt may carry only
the manifest identity, hashes and decision, never the raw body.

`READY_FOR_BOUNDED_HISTORY_CAPTURE` is possible only after a later authorized
runtime pilot verifies exact metadata identity and 96 observed, unique,
ascending, 900-second-aligned, gap-free natural bars. OHLC values must be
positive and internally consistent; volume must be observed in USD.

Missing intervals remain `UNKNOWN`. Carried-forward prices and zero-volume
imputation are forbidden. A gap, duplicate, alignment failure, incomplete
panel, wrong identity, absent raw manifest or raw-hash mismatch produces
`REDESIGN_PUBLIC_HISTORY_ROUTE` or `CLOSE_PUBLIC_HISTORY_ROUTE`.

A passed pilot is not the A4 feasibility capture: the inherited requirement of
at least 12 complete retained 24-hour panels remains unchanged.

## Retention, authority and non-claims

Failed or unusable raw evidence from a later pilot is retained for 30 days
with its failure receipt. Evidence used by an accepted dataset, trial or owner
decision is retained with dependent research and hashes.

This atom makes zero provider/API/RPC/WSS calls, uses no credential, retains
zero provider bodies, reads no R2/R3 value or path, creates no wallet, signer
or transaction, spends no cash, and changes no dependency, Catalog, registry
or Project Source.

It grants no provider-read authority. The exact approval phrase remains a
disabled template until a later separate owner instruction authorizes exactly
the two canonical requests and their raw-retention terms. It makes no
representative-sample, PIT, alpha, execution, PnL, NetReturn, cashflow or
TASK-27-completion claim.
