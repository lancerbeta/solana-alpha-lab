# TASK-21 H24 minimum-age sentinel capture contract v1.1

`T21-A6S_H24_FOREGROUND_CAPTURE_V1` captures one supplemental H24-plus quote
panel for the frozen outcome-blind sentinel. It is not a replay of the missing
H6 panel and does not make the T1 members complete.

## Time semantics

The latest immutable H0 trigger is the anchor. Capture is forbidden before
`2026-08-01T07:50:34.414367Z`, exactly 86,400 seconds later. There is no
ten-minute expiry and no operator-lateness gap. A run after the minimum age
must record the anchor, not-before timestamp and exact actual elapsed seconds.
It may label the observation only as `MINIMUM_AGE_24H_PLUS`, never as an exact
fixed-clock H24 measurement.

Reaching the minimum age makes the atom due but grants no provider authority.
The foreground run still requires the exact execution phrase, current healthy
recovery evidence and all local caps. A stale recovery proof blocks before
transport and is refreshed under a separate authority boundary.

## Sentinel and caps

The three immutable H0 admission events are validated in their frozen order.
Exactly one sentinel is selected by
`first_reliable_available_at`, `observed_at`, `nomination_event_id`, without
quote, route, price, terminal or hypothesis outcome input.

The atom permits at most one panel, eight quote calls, eight modeled provider
credits, 300 wall seconds, 3 MiB received bytes and 16 MiB create-only local
evidence. It preserves every terminal result, including no-route and stopped
evidence. It performs no trade or swap.

## Next boundary

H72 and H168 are `DEFERRED_TRIGGER_ONLY`. H24 creates no later active gate,
deadline, scheduler or provider authority. A later persistence observation
requires a named consumer or hypothesis need, fresh whole-task budget proof
and separate exact user authority.

Catalog remains pending `T21-A7`. This contract itself authorizes no network,
provider/API/RPC/WSS or Drive call; no capture, cash spend, credential use,
scheduler, deployment, wallet, signer, transaction, commit, push, PR, merge,
UI or destructive action.
