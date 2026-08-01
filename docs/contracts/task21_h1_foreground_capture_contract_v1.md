# TASK-21 H1 foreground capture contract v1

`T21-A6S_H1_FOREGROUND_CAPTURE_V1` records the second execution-capacity
panel for the exact three members admitted by H0. It changes neither
membership nor the hypothesis and never backfills a missed window.

## Frozen clock and population

The tracked H0 acceptance receipt, its local runtime receipt, admission events
and active gate are exact protected inputs. H1 may execute only from
`2026-07-31T08:50:34.414367Z` through
`2026-07-31T09:00:34.414367Z`, inclusive. Before the first instant it performs
no write or provider call. After the last instant it writes one explicit local
gap receipt with zero provider calls; capture and rescheduling are forbidden.

H1 uses the three H0 members in their frozen order. No quote, route, price,
terminal class or hypothesis outcome may change membership or ordering.

## Bounded panel

Within the live window each member receives the same four USD notionals and
dependent reverse-sell construction as H0. Limits remain:

- at most three panels and eight keyless Jupiter quote calls per panel;
- at most 24 calls and 24 modeled credits total;
- concurrency one, retries zero, 2.2-second minimum pacing;
- 20-second request timeout and 300-second foreground wall cap;
- at most 3 MiB received and 16 MiB durable local evidence;
- create-only evidence under `local/task21_forward/h1_capture`.

The only provider surface is
`GET https://api.jup.ag/swap/v1/quote`. Authentication, another endpoint,
transaction/instruction content, cap drift or unhealthy recovery stops before
the affected call. Partial evidence after the first call is retained.

## Boundary after H1

A complete H1 creates a foreground H6 gate at the frozen H0 anchor plus 21,600
seconds, with a ten-minute window. A missed H1 creates no replacement H1
window. No scheduler, daemon or unattended process is installed.

## Authority and non-claims

Only an explicit user authorization naming
`T21-A6S_H1_FOREGROUND_CAPTURE_V1`, revalidated inside the live window,
authorizes the provider calls. Repository standing autonomy covers the
offline implementation and receipts but does not supply provider authority.

Cash, credentials, Drive actions, deployment, wallet, signer, transaction,
swap execution, Git transport, Catalog A7 and hypothesis unsealing remain
outside this atom. H1 records quotes; it does not establish fills, positions,
PnL, alpha, market-wide validity or dataset sufficiency.
