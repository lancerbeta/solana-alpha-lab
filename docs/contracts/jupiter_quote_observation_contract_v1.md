# Jupiter quote observation contract v1 — TASK-10 Atom 2

## Status and purpose

This contract freezes `T10-A2_LOCAL_WRITE_ONLY` after the read-only Entry Gate
verdict `START_WITH_PATCH`. It defines a bounded, offline-first compatibility
pilot for point-in-time buy and reverse-sell quote evidence.

The estimand is:

> For one TASK-09 follow-up mint and one exact USDC atomic notional, did a
> provider return an executable buy quote, and did it then return an executable
> sell quote for the exact atomic amount quoted by the buy response?

The evidence remains:

```text
Touch != Fillable != RealizedVWAP != Net != PathRisk
```

A quote is not a fill, transaction, landing result, realized cashflow or alpha.
This atom performs no provider/API/RPC/WSS call, dependency change, raw-data
write, credential use, transaction action, Git publication or payment.

## Accepted Entry Gate patch

Official Jupiter documentation was observed read-only on 2026-07-28.

- Current Swap V2 is the recommended family.
- V2 `/order` returns an assembled transaction and requires taker-coupled
  semantics.
- V2 `/build` returns transaction instructions.
- Legacy Metis `/swap/v1/quote` is quote-only but is no longer actively
  maintained.
- Official authentication documentation is not internally sufficient to
  prove that a future request will remain keyless. Any authentication or
  account requirement is therefore a stop, not an invitation to create an
  account or use a key.

TASK-10 does not silently weaken its transaction boundary. Current V2
`/order` and `/build` are ineligible for the first quote-only pilot.

The only future compatibility candidate is:

```text
GET https://api.jup.ag/swap/v1/quote
```

That candidate may be probed only under a separate exact external-call and raw
write authority. Any evidence would be
`LEGACY_QUOTE_COMPATIBILITY_ONLY`; it would not prove that a supported current
production path exists. There is no automatic fallback from the legacy quote
surface to V2.

Primary source pointers:

- `https://developers.jup.ag/docs/swap`
- `https://developers.jup.ag/docs/api-reference/swap/v1/quote`
- `https://developers.jup.ag/docs/llms.txt`

## Frozen quote panels

The input quote mint is canonical Solana USDC:

```text
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

USDC has six decimals. The exact buy inputs are:

| USD notional | USDC atomic input |
|---:|---:|
| 10 | 10,000,000 |
| 25 | 25,000,000 |
| 50 | 50,000,000 |
| 100 | 100,000,000 |

Each panel is sequential:

1. `BUY`: USDC atomic input -> selected TASK-09 mint.
2. `SELL`: the exact `outAmount` atomic value from the accepted buy response
   -> USDC.

Float arithmetic, decimal re-rounding and a separately estimated sell input
are forbidden. If the buy leg is not `QUOTE_AVAILABLE`, its sell leg is not
requested and is recorded as `NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED` in the
pilot receipt, not as `NO_ROUTE`.

The selected mint, its decimals and its TASK-09 raw/evidence lineage must be
frozen before the external atom. Selection by observed profitability,
subsequent price movement or successful routing is forbidden.

## Request and route identity

Every attempted request receives:

- a canonical JSON request representation;
- `request_hash = SHA-256(canonical_request_json)`;
- an idempotency key binding provider contract version, side, mints, exact
  atomic amount and attempt ordinal;
- a business key shared by the buy and dependent reverse-sell panel;
- a provider version that explicitly includes `legacy_metis_v1_quote`.

For `QUOTE_AVAILABLE`:

- `route_count` is the exact length of `routePlan`;
- `route_id` is SHA-256 of canonical JSON for the complete `routePlan`;
- empty or missing `routePlan` cannot be promoted to an available quote;
- `contextSlot` remains nullable but must be retained when present.

Provider-specific route legs and `priceImpactPct` remain in redacted immutable
raw evidence under schema v1. They are not invented as normalized columns.

## Point-in-time timestamps

The pilot records:

| Contract timestamp | TASK-05 projection |
|---|---|
| `event_at` | `requested_at` |
| `observed_at` | `response_at` |
| `available_at` | `available_to_strategy_at` |
| `ingested_at` | `ingested_at` |
| `first_reliable_available_at` | `first_reliable_available_at` |
| provider context slot | `context_slot` |

For a response-bearing attempt:

```text
requested_at <= response_at
             <= first_reliable_available_at
             <= available_to_strategy_at
             <= ingested_at
```

For `TIMEOUT`, `response_at` is null. The timeout classification time becomes
`first_reliable_available_at`; missing response bytes never become a synthetic
empty response or zero amount.

## Typed terminal states

TASK-05 `quote_attempts` is reused without schema change:

- `QUOTE_AVAILABLE` — positive route count, route identity and quoted output;
- `NO_ROUTE` — response received, explicit no-route disposition, route count
  zero and no quoted output;
- `PROVIDER_ERROR` — typed HTTP/provider failure such as rate limiting or 5xx;
- `INVALID_RESPONSE` — schema mismatch, stale response, forbidden
  transaction/instruction payload or incoherent quote fields;
- `TIMEOUT` — no response before the frozen timeout.

Required distinctions:

- missing is not zero;
- `NO_ROUTE` is not inferred from timeout, 4xx, 5xx, rate limit or schema
  failure;
- stale data is `INVALID_RESPONSE`, never an available quote;
- an unavailable buy does not manufacture a reverse-sell attempt;
- retry count is zero.

## Fee and price-impact accounting

The provider `outAmount` is stored exactly as returned. Embedded route
economics and price impact are not subtracted from it a second time.

Normalized fee fields are populated only when one fee mint and the inclusion
semantics are proven by the pinned provider contract. Otherwise:

- `provider_fee_atomic`, `platform_fee_atomic`, `fee_mint` and
  `included_in_output_amount` remain null together;
- provider route fee details stay in raw evidence;
- `quality_flags` records `PROVIDER_ROUTE_FEE_DETAIL_RAW_ONLY`.

`slippageBps` and `otherAmountThreshold` are constraints, not realized costs.
They are retained in raw evidence and never subtracted as PnL.

## Raw evidence and security boundary

TASK-06 redaction-before-storage, deterministic raw/content identity,
append-only revisions and manifests are mandatory.

- Raw response bytes remain outside Git.
- Tracked fixtures contain synthetic values only.
- API keys, accounts, private endpoints and secrets are forbidden.
- A transaction or instruction payload on the selected quote-only path is
  `INVALID_RESPONSE/TRANSACTION_PAYLOAD_FORBIDDEN` and stops the run after the
  typed raw envelope is retained.
- No transaction is decoded, constructed, simulated, signed, submitted or
  landed.

## Cheapest future falsifier and caps

The future external atom, if separately authorized, is bounded by:

- one selected mint;
- four buy panels and at most four dependent sell panels;
- at most eight HTTP requests total;
- concurrency one;
- retries zero;
- wall time at most 600 seconds;
- received response bytes at most 1,048,576;
- total durable raw storage at most 5,242,880 bytes;
- API keys/accounts/credentials zero;
- provider credits zero;
- cash spend USD 0;
- wallet/signer/transaction actions zero.

Stop immediately on:

- authentication or account requirement;
- V2-only, transaction-only or instruction-only response surface;
- unexpected response keys that cannot be classified fail-closed;
- response/byte/time cap exhaustion;
- dependency or schema change requirement;
- any request outside the exact mint/panel set.

No retry, alternate provider, paid plan, longer collection or runtime
implementation is inherited.

## Schema and Catalog mapping

- `SCHEMA-T05-REL-QUOTE-ATTEMPTS-001` is the first durable projection.
- `SCHEMA-T05-REL-EXECUTION-ATTEMPTS-001` remains forbidden in TASK-10 Atom 2
  and in the quote-only pilot.
- `CONTRACT-T06-RAW-STORAGE-001` owns raw durability and redaction.
- `EVIDENCE-T09-PUMPSWAP-TOUCH-RECEIPT-001` supplies Touch lineage only.
- TASK-09 observations do not become Fillable or `NO_ROUTE`.

The contract, deterministic fixture and offline test are registered as:

- `CONTRACT-T10-JUPITER-QUOTE-OBSERVATION-001`;
- `FIXTURE-T10-JUPITER-QUOTE-OBSERVATION-001`;
- `TEST-T10-JUPITER-QUOTE-OBSERVATION-001`.

Named consumers are TASK-10, TASK-13, TASK-18/19, TASK-25/26, TASK-36..40 and
TASK-43..47.

## Atom boundary and next decision

Atom 2 is complete only when the contract, fixture, existing `QuoteAttempt`
projections, Catalog records and generated navigation validate offline.

The next candidate atom is
`T10-A3_LOCAL_QUOTE_LOGGER_IMPLEMENTATION`. It requires a separate exact
managed write set. The bounded external quote run remains a later and separate
`EXTERNAL_ACCOUNT_API_RPC + RAW_WRITE` authority boundary.
