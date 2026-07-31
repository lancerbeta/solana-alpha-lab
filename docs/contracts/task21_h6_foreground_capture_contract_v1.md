# TASK-21 H6 foreground capture or gap-close contract v1

`T21-A6S_H6_FOREGROUND_CAPTURE_V1` preserves the third observation horizon for
the exact three H0 members. It may either capture one bounded H6 panel per
member inside the frozen window or, after that window, record one explicit gap.
It never reschedules or backfills H6.

## Frozen inputs and clock

H0 membership and order, H0/H1 runtime receipts, the active H6 marker and the
runtime-recovery receipt are protected inputs. The H6 window is exactly
`2026-07-31T13:50:34.414367Z` through
`2026-07-31T14:00:34.414367Z`, inclusive.

- Before the window: no provider call and no durable output.
- Inside the window: capture requires both a separate exact user provider gate
  and recovery health with backup age at most 24 hours and restore-proof age at
  most 168 hours.
- After the window: provider execution is forbidden; write one create-only gap
  receipt with zero provider calls, no backfill and no silent reschedule.

At H6 open the accepted backup timestamp was already about 27.94 hours old.
Therefore H6 was not safely executable without a separately authorized fresh
backup/read-back. The active marker itself grants neither Drive nor provider
authority.

## Bounded live shape

If both gates had passed inside the window, the only allowed provider surface
would have been `GET https://api.jup.ag/swap/v1/quote`: three panels, eight
calls per panel, 24 total modeled credits, concurrency one, retries zero,
2.2-second pacing, 300-second foreground cap, 3 MiB received and 16 MiB local
create-only evidence. Membership and hypothesis outcome remain frozen.

## Forward boundary

Whether H6 is captured or explicitly missing, the next independent sentinel is
H24 at the latest H0 anchor plus 86,400 seconds:
`2026-08-01T07:50:34.414367Z` through
`2026-08-01T08:00:34.414367Z`. H6 absence is retained as missing evidence; H24
must not fabricate or replace it.

No scheduler, daemon, Drive action, transaction, swap, cash spend, credential,
Catalog A7 transaction, commit, push, PR or merge is authorized by this
contract. Quotes do not establish fills, positions, PnL, alpha or dataset
sufficiency.
