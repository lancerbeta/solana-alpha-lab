# TASK-27 — Historical price/volume research-screen contract v1

## Purpose

This offline contract freezes the smallest admissible historical pool
price/volume unit for deciding whether a later data collection can support a
point-in-time (PIT) research screen. It does not collect data and does not
authorize a provider request.

The sole primary label is `FORWARD_CLOSE_RETURN_1H`: percentage price change
from the close of a 15-minute entry bar to the close exactly one hour later.

## Observation unit

One observation is a `pool_interval` with immutable identity:

- `network`, `pool_id`, `base_token_id`, `quote_token_id`, `dex_id`;
- `observation_scope=POOL`; token-level bars cannot substitute for pool bars;
- `interval_start_at` and fixed `interval_seconds=900`;
- `open`, `high`, `low`, `close`, `volume`, and `volume_currency`;
- `event_time`, `observed_at`, `available_at`, and `ingested_at`.

The timeline must preserve `event_time <= observed_at <= available_at <=
ingested_at`. A row without an established `available_at` may be retained as
descriptive evidence but cannot support a PIT-known price label.

## Label rule

For an entry interval beginning at `S`, the entry price is its close at `S +
15m`. The terminal price is the close of the interval beginning at `S + 60m`,
which closes at `S + 75m`. The label is:

`(terminal_close - entry_close) / entry_close`

The label is `KNOWN` only when the entry interval and the four successor
intervals beginning at `S + 15m`, `S + 30m`, `S + 45m`, and `S + 60m` are all
observed, contiguous, and PIT-admissible. Any gap, unknown availability, or
unobserved successor requires `UNKNOWN`; it never becomes zero or flat.

## Missingness and quality rules

- `MISSING_UNKNOWN` cannot carry OHLC or a zero-volume substitute.
- Carried-forward price data is forbidden.
- Observed OHLC values must be positive and satisfy `low <= min(open, close)`
  and `high >= max(open, close)`.
- A non-900-second grid or a non-contiguous successor chain is invalid.
- The fixture is synthetic only. It contains no retained provider response,
  public-pool identifier, or real market observation.

## Non-claims

This contract does not establish a signal, alpha, trade, order, route, quote,
fill, inventory, PnL, realized result, `NetReturn`, or owner cashflow. A
historical price label does not imply executable execution. It does not grant
provider/API/RPC/WSS access, R3 access, credential use, wallet/signer activity,
transaction activity, cash spend, Catalog mutation, Project Source mutation,
or strategy promotion.

## Acceptance boundary

The v1 acceptance is satisfied only by deterministic offline schema validation
and synthetic adversarial tests. Later data collection needs a separate,
explicit authority packet naming source, universe, date range, query/storage
cap, retention, and the owner decision it will serve.
