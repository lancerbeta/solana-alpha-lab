# TASK-30 OHLCV boundary semantics decision contract v1

## Consumer and decision

The consumer is a future named history-feasibility or TASK-30 entry gate. This
contract records whether the retained T30-A0 response can establish the time
coverage of a continuous 15-minute panel. It is an offline semantic decision,
not a market-data acceptance, trial, backtest, strategy, liquidity result,
execution route, or PnL decision.

## Bound observation

The only raw input is the `T30-A0` GeckoTerminal response retained outside Git
under its recorded retention rule. It is bound only by SHA-256
`cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163`.

The frozen request asked for 96 fifteen-minute records before
`1786186800`. The response had 96 records, a returned timestamp grid from
`1786101300` through `1786186800`, and 67 zero-volume records. These are
observed response-shape facts only. They do not prove the meaning of a candle
timestamp or that a zero-volume record is an observed no-trade event.

## Required semantic split

Exactly two candidate timestamp models must be retained:

| Model | Record represented by timestamp `t` | Implied coverage | Result |
| --- | --- | --- | --- |
| `START_LABELED` | `[t, t + 900)` | `[1786101300, 1786187700)` | Does not match the requested target |
| `END_LABELED` | `[t - 900, t)` | `[1786100400, 1786186800)` | Would match the target |

The one response cannot select between these models. `END_LABELED` is a
conditional explanation, not a vendor contract.

## Terminal decision and next evidence

The only v1 decision is `UNRESOLVED_INTERVAL_LABEL_SEMANTICS`. It requires
`INDEPENDENT_EXACT_TIMESTAMP_SEMANTICS_PROOF` before any continuous-panel,
PIT-admissibility, explicit-no-trade, or TASK-30 trial claim. A repeated raw
download, fallback provider, endpoint probe, or a silent one-bar shift is not
that proof and is outside this contract.

## Authority and non-claims

This atom allows only tracked offline contract/test/Catalog work and ordinary
Git delivery. It authorizes zero provider/API/RPC/WSS calls, credentials,
R2/R3, dependency changes, wallet/signer/transaction actions, cash spending,
TASK-30 trial/acceptance, Project Sources modification, or numeric PnL and
NetReturn claims.

`zero_volume_record_count=67` remains `OBSERVED_ZERO_VOLUME_NOT_PROVEN_NO_TRADE`.
No missing state may become zero, flat, continuous, settled, fillable, or
PIT-admissible through this decision.

## Acceptance

Acceptance requires a strict schema, synthetic golden fixture, deterministic
evaluator, explicit rejection of selecting either timestamp model, external or
trial authority, zero-volume promotion, continuous/PIT claims, Catalog
registration, and a Project Sources disposition of `NO_CHANGE`.
