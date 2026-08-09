# TASK-30 Birdeye route hold and forward price capture decision contract v1

## Purpose and consumer

This offline contract records the exact observed Birdeye rate-or-quota limit
and defines one future owner decision boundary for a narrow price/volume
capture candidate. Its sole consumer is
`FUTURE_TASK30_FORWARD_PRICE_CAPTURE_ENTRY_GATE`.

The decision is not a retry authorization, a provider rejection, a historical
panel, a collector, a scheduler, a strategy, or TASK-30 acceptance.

## Historical Birdeye route

The exact A5R1 OHLCV request received HTTP 429 after its pair overview request
succeeded. The route is therefore `HOLD_NO_AUTORETRY`:

- HTTP 429 is not interpreted as no history, unsupported pair or unsupported
  provider surface;
- this contract authorizes no retry, fallback or provider switch;
- reopening requires documented quota or access recovery and a new exact owner
  external authorization.

## Future capture candidate

The only candidate is public Solana pool
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.

If a later provider-specific owner gate authorizes it, the initial pilot can
observe at most one response per closed 900-second UTC slot for 86,400 seconds,
or 96 scheduled observations. The provider is `NOT_SELECTED`, and a scheduler
is `PLANNED_NOT_BUILT`.

Every observation must retain slot open and close time, actual observation and
ingestion time, request identity, response hash, provider response timestamp
when present, and terminal state. A provider candle label remains exactly as
received. A missing slot remains an explicit typed gap and is never backfilled,
converted to zero volume or called no trade.

## Reuse and non-claims

The future implementation may adopt content-addressed manifests, idempotent
slot identity, physical caps, typed gaps and recovery/daily-health concepts
from TASK-20/TASK-21. It must not reuse Jupiter quote values, the TASK-21
technical probe as admission, a TASK-21 endpoint or its execution-capacity
run plan.

This atom has zero provider/API/RPC/WSS calls, credential uses, raw-data writes,
scheduler/background processes, dependencies, wallet/signer/transaction
actions, cash spend, TASK-30 trial/acceptance and Project Sources changes.
It makes no continuous-panel, PIT-admissibility, no-trade, provider-selected,
scheduler-running, alpha or numeric NetReturn claim.

## Next boundary

`EXACT_PROVIDER_SELECTION_AND_24H_CAPTURE_GATE_REQUIRED` is a new owner
decision. It must name one provider, endpoint, transport, request cap,
retention location and stop conditions before any external action.
