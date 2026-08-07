# T27-A0-A2 — Historical price/volume research-screen contract: design

## Decision

Create one offline, versioned contract for a future historical Solana pool
price/volume sample.  Its single primary research label is the percentage
change from the close of a 15-minute entry bar to the close exactly one hour
later.  This is a research screen only: it is not a trade, fill, PnL,
NetReturn, strategy approval, or authority to retrieve data.

## Why this boundary

TASK-25/26 evidence established sparse price/quote observations but not a
continuous historical price series, fills, settlement, or cashflow.  A
contract-first data gate is the cheapest way to decide whether later historical
collection can support a PIT-safe price/volume research screen without
pretending that sparse observations answer that question.

## Chosen approach

The implementation will follow the existing Task-25 contract pattern:

1. A Markdown contract states semantic invariants and non-claims.
2. A YAML configuration freezes the admissible unit, 15-minute interval,
   one-hour primary label, coverage rules, and forbidden inference paths.
3. A JSON Schema validates a synthetic payload only; it does not describe an
   acquired provider dataset.
4. A tracked synthetic fixture and one Python test module prove both the
   accepted path and adversarial rejections.
5. A machine-readable acceptance receipt records the exact offline result.

No runtime component, provider adapter, data downloader, database migration,
Catalog update, Source update, or strategy implementation is part of this
atom.

## Future data contract

The natural observation is one `pool_interval`:

- immutable identity: `network`, `pool_id`, `base_token_id`, `quote_token_id`,
  `dex_id`, and `interval_start_at`;
- interval: exactly 900 seconds, with `interval_end_at` derived from its start;
- values: `open`, `high`, `low`, `close`, `volume`, and `volume_currency`;
- time provenance: `event_time`, `observed_at`, `available_at` when the source
  can establish it, and `ingested_at`;
- data-state: `OBSERVED`, `EXPLICIT_NO_TRADE`, or `MISSING_UNKNOWN`.

`MISSING_UNKNOWN` is never converted to zero volume, a flat candle, a carried
forward price, or a settled outcome.  If source availability cannot be
established, the row may be retained descriptively but cannot support a
PIT-known-at-entry claim.

For an entry interval that starts at `S`, entry price is that interval's close
at `S + 15m`.  The one-hour terminal price is the close of the interval starting
at `S + 60m`, which closes at `S + 75m`.  The label is:

`(terminal_close - entry_close) / entry_close`

It is admissible only when the four successor 15-minute intervals starting at
`S + 15m`, `S + 30m`, `S + 45m`, and `S + 60m` are all observed and contiguous.
Otherwise its state is `UNKNOWN`.

## Failure handling and non-claims

The contract must reject or mark unknown:

- duplicate interval identities;
- a non-15-minute grid or non-contiguous forward window;
- non-positive prices or an OHLC ordering violation;
- substituted zero volume or carried-forward OHLC for missing data;
- invalid provenance ordering (`event_time > available_at > ingested_at`);
- mixing token-level observations with a pool-level identity;
- labelling from an incomplete future window;
- interpreting a price label as a fill, executable route, realized PnL,
  NetReturn, or alpha.

The contract has no provider authorization.  It contains no raw GeckoTerminal
response, no wallet or signer material, no RPC/WSS/API call, no R3 interaction,
and no numeric realized or modelled NetReturn.

## Planned files and validation

After this written design is reviewed, the implementation write set is:

- `docs/contracts/task27_price_volume_research_screen_contract_v1.md`
- `configs/task27_price_volume_research_screen_contract_v1.yaml`
- `catalog/schemas/task27_price_volume_research_screen.schema.json`
- `tests/fixtures/task27/price_volume_research_screen_v1.json`
- `tests/test_task27_price_volume_research_screen_contract.py`
- `docs/evidence/task27/a0a2_price_volume_research_screen_contract_acceptance_v1.json`

The test will first encode the rejected cases, then validate the good synthetic
case and the acceptance receipt/hash bindings.  Delivery validation will use
the repository's tracked-only preflight after the final commit; GitHub CI is an
independent later read-back, not part of this offline atom.

## Acceptance and recovery

Success means the synthetic fixture and tests make the data/label semantics
deterministic, and every forbidden inference above is rejected.  It does not
mean historical data has been collected or that TASK-27 has been started or
accepted canonically.

If later public data cannot meet the contract, the correct outcome is
`DATA_NOT_ADMISSIBLE_FOR_PIT_PRICE_SCREEN`, not a relaxed label or an inferred
zero/flat path.  A later provider-read proposal must name its source, universe,
date range, call and storage cap, retention, and owner decision separately.
