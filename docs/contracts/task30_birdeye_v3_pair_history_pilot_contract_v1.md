# TASK-30 Birdeye V3 pair history pilot contract v1

## Purpose and consumer

This is an offline preparation packet for one future owner decision. Its
consumer is `FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE`. It specifies no more than
two dependent Birdeye V3 `GET` requests so that a later, separately authorized
provider read can falsify the data route without hidden retries, provider
substitution, or key handling in Git.

The v1 decision `OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE` means only that
the packet is internally consistent. It does not grant owner authority, prove
local credential presence, execute a request, or establish a historical panel.

## Frozen input identity

The sole candidate is the public Solana PumpSwap pool
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, with base mint
`DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and quote mint
`So11111111111111111111111111111111111111112`. These values are bound to
`docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json`.
That earlier public identity evidence binds the candidate pool; it does not
claim that Birdeye indexes it or that Birdeye emits equivalent price fields.

## Future external stage — not authorized by this contract

The later owner gate may allow **at most two** credentialed `GET` requests. The
credential is injected only into a local header transport at execution time;
its value is never read into a tracked file, log, URL, receipt, or chat.

| Order | Read ID | Endpoint path | Fixed inputs | Stop rule |
| --- | --- | --- | --- | --- |
| 1 | `PAIR_OVERVIEW_IDENTITY_READ` | `/defi/v3/pair/overview/single` | `x-chain=solana`; address is the frozen pool; `ui_amount_mode=raw` | Any non-200 stops the chain; no second read. |
| 2 | `PAIR_OHLCV_RANGE_READ` | `/defi/v3/ohlcv/pair` | Same address; `type=15m`; `[1786100400,1786186800)`; `mode=range`; `padding=true`; `outlier=true`; `inversion=false` | Eligible only after the first observed HTTP 200; non-200 is retained as the route outcome. |

Each read has exactly one attempt. There is no retry, fallback provider,
Helius route, Solana Tracker route, Gecko route, token-level substitution,
request fan-out, or provider SDK. Any response body available after a future
authorized read is retained outside Git under the existing A4 retention
boundary with a secret-redacted request receipt. This atom creates no raw bytes
or storage path.

The first response can only establish that Birdeye accepted the input address
as a pair-level request on Solana. It must not overwrite the prior frozen
base/quote/DEX identity. The second response can only establish the observed
behavior of this exact request. A 200 response does not by itself prove a
documented REST `15m` contract, USD price unit, empty-bucket meaning, 96-bar
coverage, no-trade intervals, point-in-time availability, or admissibility for
research.

## Explicit unknowns

Until a separately authorized response is validated, all of the following stay
`UNPROVEN`:

- whether REST accepts the candidate `type=15m` parameter for this pair;
- whether Birdeye has indexed the candidate pair at the requested route;
- price unit and field interpretation;
- semantics of padded empty intervals;
- complete 96-bucket coverage and timestamp-boundary behavior;
- first reliable availability, revision behavior, PIT admissibility, alpha, and
  any TASK-30 trial result.

Missing, response absence, non-200, absent fields, or malformed bars remain
explicit gaps. They are never converted to zero volume, no trade, flat price,
or successful settlement.

## Future owner gate

Before any actual request, a future owner message must name Birdeye, the exact
pool, the two-request maximum, the fixed window, local header-only credential
transport, A4 outside-Git retention, the no-retry/no-fallback rule, and the
prohibited actions. It must also separately attest key presence without
revealing a value. A missing key, non-200, malformed payload, or unresolved
identity conflict is a stop condition, not an invitation to try another source.

## Authority and non-claims

This atom permits only tracked offline contract, configuration, schema,
fixture, evaluator, evidence, Catalog, test, and ordinary Git delivery work.
It performs zero provider/API/RPC/WSS calls, credential uses, raw-data writes,
R2/R3 reads, dependencies, wallet/signer/transaction actions, cash spend,
TASK-30 trial or acceptance actions, or Project Sources changes.

It does not build an HTTP client, a collector, a dashboard, a research panel,
a strategy, execution logic, PnL, or numeric NetReturn. Project Sources remain
`NO_CHANGE` because this is neither canonical TASK-30 completion nor a release
candidate.
