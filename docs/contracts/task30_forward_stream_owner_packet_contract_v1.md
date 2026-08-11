# TASK30-FORWARD-STREAM-OWNER-PACKET-V1

## Purpose

This contract defines an offline-only proposal for a future bounded
transaction-stream technical pilot.  A valid packet means only that an owner
can inspect a precise future external-read gate.  It does not provide that
authority.

## Proposed envelope

| Boundary | Frozen policy |
| --- | --- |
| Provider candidate | `HELIUS_TRANSACTION_SUBSCRIBE` / `PROPOSED_NOT_SELECTED` |
| Transport candidate | `WSS_JSON_RPC` |
| Candidate method | `transactionSubscribe` |
| Candidate wire options | `commitment=confirmed`, `encoding=jsonParsed`, `transactionDetails=full`, `maxSupportedTransactionVersion=0`, `failed=false`, `vote=false` |
| Target | frozen Solana pool and base mint from TASK-30 A13 |
| Connection/subscription cap | exactly `1` / exactly `1` |
| Capture cap | maximum `1,200` seconds and `500` notifications |
| Monitoring | `LOCAL_WORK_CODEX_FOREGROUND` only; no unattended scheduler |
| Retention | `A4`; exact absolute root is supplied only to a separately authorised future run and stays outside Git |
| Recovery | retry, reconnect, fallback and automatic reconciliation are forbidden |

## Terminal truth

The future run must emit one of:

`PILOT_NOT_AUTHORIZED`, `CONNECTION_OR_AUTH_REJECTED`,
`SUBSCRIPTION_REJECTED`, `NO_OBSERVED_TX_NO_EMPTY_CLAIM`,
`OBSERVATION_RETAINED_TECHNICAL_ONLY`, `TRANSPORT_LOST_UNKNOWN`, or
`RETENTION_FAILED_STOP`.

No terminal state itself proves empty market activity, coverage completeness,
price/volume data, PIT eligibility, hypothesis evidence, a trial, execution,
settlement, PnL or NetReturn.  In particular, a transport loss is `UNKNOWN`;
it may be reconciled only through a new exact owner-authorised source and
cannot be erased by a retry, reconnect, fallback or projection.

## Future owner phrase template

Only this later phrase template may authorise a pilot, after its exact date,
retention root and current provider entitlement are reviewed:

```text
T30-A13P_FORWARD_STREAM_PILOT_V1; pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_wss_connections=1; max_subscriptions=1; max_open_seconds=1200; max_notifications=500; retention=A4; retry=false; reconnect=false; fallback=false
```

The phrase authorises neither a wallet, transaction, cash action, retry nor
reconciliation.  Its future receipt must contain safe request/body hashes and
the exact, non-secret retention binding; neither is present here.

## Offline invariants

- all authority counters are zero or false;
- durable data contains no endpoint, URL, credential or raw provider payload;
- candidate provider selection remains proposal-only;
- DEX program/route remains `OWNER_VERIFIED_ROUTE_REQUIRED`, never inferred
  from the pool address;
- Source disposition is `NO_CHANGE`; and
- `READY_FOR_OWNER_EXTERNAL_READ_GATE_WITH_LIMITATIONS` does not grant
  external authority.
