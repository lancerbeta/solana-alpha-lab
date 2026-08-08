# T27-A0-A7 — Exact single-pool selection and pilot-read packet design

## Decision

Prepare one repository-tracked, deterministic offline packet that freezes the
owner-nominated Solana pool and the cheapest future public-read pilot capable
of falsifying the GeckoTerminal historical OHLCV route. The packet does not
contact GeckoTerminal, retain a provider response, or grant external-read
authority.

The exact atom is
`T27-A0-A7_EXACT_SINGLE_POOL_SELECTION_AND_PILOT_READ_PACKET_V1`. It inherits
the A4 capture caps and the A6 owner-review boundary without weakening either.

## Owner-nominated target

The sole target is the pool identified by:

- network: `solana`;
- pool address: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- owner-supplied page:
  `https://www.geckoterminal.com/solana/pools/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- selection class: `OWNER_NOMINATED_SINGLE_POOL`;
- universe description:
  `ONE_NON_REPRESENTATIVE_TECHNICAL_FEASIBILITY_TARGET`.

The page observation suggests `PumpSwap` and `Cope/SOL`, but those labels are
not promoted to verified identity facts until the future metadata response
matches them. Pool nomination is not token endorsement, market-universe
selection, representativeness, alpha evidence, or permission to trade.

## Approaches considered

1. Retain no raw response and record only parsed candles. Rejected: this would
   make provider semantics, gaps, revisions, and parsing impossible to audit.
2. Execute the full A4 capture immediately. Rejected: it would spend the
   request and operator budget before the source shape and missing-interval
   behavior are proven for the nominated pool.
3. Freeze one exact metadata request and one exact 24-hour OHLCV request, then
   require a separate owner gate for execution. Selected: it is the cheapest
   falsifier of identity, response shape, natural continuity, and raw-evidence
   retention.

## Exact future pilot

The offline packet will describe exactly two future keyless public GETs against
`https://api.geckoterminal.com/api/v2`:

1. one pool-metadata request for the exact Solana pool address; and
2. one pool OHLCV request using `timeframe=minute`, `aggregate=15`,
   `limit=96`, `currency=usd`, `token=base`, and
   `include_empty_intervals=false`.

The OHLCV request must use one frozen `before_timestamp` aligned to a
15-minute UTC boundary. A floating "latest" request is invalid because it
cannot be replayed or compared deterministically.

The public API is keyless. No credential or account is requested or stored.
The future request packet remains invalid until a later exact owner approval
names the request ID, frozen timestamp, two exact URLs, raw-manifest identity,
retention boundary, and request count.

## Evidence and retention model

Future raw response bytes and minimal response metadata will live outside Git
under an ignored run directory. The tracked repository may retain only the
request specification, content hashes, manifest/receipt, validation result,
and decision. No machine-specific absolute path enters a tracked artifact.

The raw manifest binds, for each request:

- stable request and run IDs;
- method and canonical URL with no secret-bearing query values;
- requested-at, response-started-at, response-completed-at, HTTP status, and
  content type;
- byte count and SHA-256 of the exact response body;
- parser/schema version and parsed-output hash;
- retention class and deletion-not-before boundary;
- failure or incompleteness reason without converting missing data to zero.

Failed or unusable raw evidence is retained for 30 days with its failure
receipt. Evidence used by an accepted dataset, trial, or owner decision is
retained with the dependent research and hashes, matching the inherited A4
policy.

## Pilot acceptance and failure rules

The pilot may emit exactly one of:

- `READY_FOR_BOUNDED_HISTORY_CAPTURE`;
- `REDESIGN_PUBLIC_HISTORY_ROUTE`; or
- `CLOSE_PUBLIC_HISTORY_ROUTE`.

`READY_FOR_BOUNDED_HISTORY_CAPTURE` requires:

- metadata identity matches the nominated network and pool address;
- base/quote token and DEX identities are explicit rather than inferred from
  the page URL;
- exactly 96 natural 15-minute bars cover one consecutive 24-hour window;
- timestamps are unique, ordered, aligned, and gap-free;
- OHLC values are positive and internally consistent;
- volume is observed in the declared currency;
- exact raw bytes and hashes are retained and reconciled to parsed output.

GeckoTerminal documents that intervals without recorded swaps can be omitted.
It also documents that `include_empty_intervals=true` fills OHLC with the
previous close and volume with zero. That option is forbidden because the A2
contract rejects carried-forward prices and `missing -> zero`. Any omitted
interval makes the pilot panel incomplete and results in `REDESIGN` or
`CLOSE`; the packet cannot silently impute, widen time, change provider, or
relax the 96-bar rule.

Passing this pilot does not satisfy A4's minimum of 12 complete retained
24-hour panels. It only proves that a later bounded capture is worth an exact
owner decision.

## Deterministic offline implementation

The implementation will add one versioned contract/config/schema, one
synthetic fixture, one focused test module, and one acceptance receipt. Tests
will include a valid synthetic packet and reject at least:

- wrong network or pool address;
- page-label inference presented as verified metadata;
- an unfrozen or unaligned `before_timestamp`;
- more or fewer than the exact two pilot requests;
- `include_empty_intervals=true`;
- a gap, duplicate, misaligned timestamp, or non-96-bar panel;
- missing raw-manifest identity or response hash;
- missing-to-zero or carried-forward substitution;
- automatic fallback provider;
- premature provider authority; and
- PIT, alpha, execution, PnL, NetReturn, or owner-cashflow claims.

The exact managed write set will be frozen in the implementation plan. No
generic ingestion framework, production collector, dependency, scheduler,
Catalog root migration, or Project Source release is justified for this
packet.

## Authority and non-claims

This atom authorizes bounded local tracked writes, deterministic synthetic
tests, ordinary Git delivery, and CI read-back under repository policy. It
authorizes zero GeckoTerminal/provider/API/RPC/WSS requests, zero retained raw
provider responses, zero credentials, zero R2/R3 reads, zero wallet/signer/
transaction actions, and zero cash spend.

It establishes neither PIT admissibility nor a representative market sample,
signal, strategy, executable route, fill, PnL, NetReturn, or owner cashflow.
The future pilot requires a new exact owner instruction after this packet is
implemented and reviewed.

## Product horizon

`NOW` is this exact offline packet: it converts the owner-nominated URL into a
reproducible, falsifiable external-read decision without crossing the material
boundary.

`WATCH` is the future runtime pilot. Activate it only after the packet passes
delivery and the owner approves the exact two requests and raw-retention
terms. A successful pilot may then justify a bounded 12-panel capture; a gap
or identity mismatch closes or redesigns the route before wider collection.
