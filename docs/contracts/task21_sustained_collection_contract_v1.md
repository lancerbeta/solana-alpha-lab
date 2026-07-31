# TASK-21 sustained forward collection and monitoring contract v1

`T21-A6_SUSTAINED_FORWARD_COLLECTION_AND_MONITORING_V1` is staged. This
contract prepares and tests the local control plane only. It does not start the
30–45-day collection.

## Entry patch

The frozen TASK-21 watchlist has zero real members. The successful A5 mint was
a technical transport probe, not a TASK-21 admission, and cannot be carried
forward automatically. A real run therefore requires an append-only,
versioned nomination and membership set before the first provider call.

The local stage is valid independently: it freezes lifecycle, coverage,
recovery, budget, incident and outcome-blindness rules. The real nomination and
capture stages remain separately gated.

## Runtime model

The collector is event-triggered and foreground. It does not poll the whole
market and does not need an always-on token feed. Each complete member has
three panels, each panel has four buy/reverse-sell quote pairs and at most
eight provider calls. Missed windows remain explicit gaps and are never
silently rescheduled.

The lifecycle is:

- `PREPARED` before exact real launch authority;
- `ACTIVE` through day 29;
- `DAY30_REVIEW` on days 30–44;
- `DAY45_STOPPED` at day 45 with no automatic extension.

At day 30, sufficient evidence becomes eligible for a separately authorized A7
freeze. Insufficient evidence continues unchanged to day 45. Day 45 always
stops; extending or redesigning requires a new plan and owner decision.

## Operational pulse and blindness

Operational monitoring may expose coverage, missingness, freshness, terminal
classes, incidents, gaps, recovery health and physical consumption. It may not
expose cost curves, token rankings, PnL, alpha or a hypothesis verdict before
the A7 freeze. Membership rules and the hypothesis estimand cannot be tuned
during collection.

Nomination events, membership events, panel receipts, gaps, incidents and
daily health receipts are append-only. An exact duplicate is idempotent; the
same identity with different bytes fails closed.

Recovery must remain `HEALTHY`. Stale backup or restore proof blocks new
windows and admissions. A full restore is still required before A7 dataset
freeze.

## Acceptance and non-claims

The deterministic fixture proves the local state machine against five
synthetic members, fifteen panels and sixty quote pairs distributed across
three UTC dates and ISO weeks. It contains no market observations and grants
no real nomination or external authority.

This stage makes zero provider/API/RPC/WSS or Drive calls, spends no cash, uses
no credentials, creates no real watchlist member or forward dataset, starts no
scheduler/background process, and performs no wallet, signer or transaction
action. A6 is only `PREPARED_LOCAL_CONTROL_PLANE`; it is not complete until
the separately authorized real collection has run and stopped.
