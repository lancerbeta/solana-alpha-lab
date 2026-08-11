# TASK-30 A11B — two-slot live shakedown owner-packet design

## Decision

Create one deterministic **offline** owner packet for a future two-slot
technical shakedown of the already observed GeckoTerminal OHLCV route. The
packet is a seatbelt, not a collector: it binds the future request shape and
stop rules, but selects no provider, starts no process and authorises no
network access.

The candidate route is carried forward only because `T30-A10` observed its
15-minute start-label semantics for the frozen pool. It remains a
`provider_candidate`, never a selected or authorised provider. The later
owner approval must bind the exact values and the execution agent must reject
any mismatch.

## Why this is the smallest useful step

`T30-A11A` proved offline that a later availability probe can distinguish a
provider/market gap from a capture-health failure. Its explicit next boundary
is an owner packet for a **two-slot** shakedown. Going straight to a 24-hour
capture would risk discovering a clock, raw-retention or monitoring defect only
after a day of ambiguous evidence. Building a generic scheduler or a provider
adapter now would solve a problem that has not been observed.

## Alternatives considered

1. **Call the route now.** Rejected: it crosses the provider boundary without
   an exact owner approval and would make the first live reading double as an
   unspecified systems test.
2. **Recommended: a narrow offline packet plus deterministic validation.** It
   carries one candidate route, two independently started closed slots, eight
   reads maximum and immediate fail-closed recovery. It leaves the actual
   provider call and the choice to the owner.
3. **Build a reusable live-capture service.** Rejected as premature: no second
   consumer, provider contract, scheduler need or evidence of repeated manual
   error exists yet.

## Future shakedown shape — proposal, not authority

| Field | Proposed value |
| --- | --- |
| Candidate route | `GECKOTERMINAL_PUBLIC_KEYLESS` A10 OHLCV path |
| Pool / network | frozen Solana pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` |
| Closed slots | exactly 2, each 900 seconds, separate foreground starts |
| Reads | offsets `+0s`, `+15s`, `+30s`, `+60s` for each slot; maximum 8 GETs |
| Query meaning | A10 start-labelled candle: request with `before_timestamp=slot_end`, then require `observed_interval_start=slot_start` |
| Retry / fallback / credentials | forbidden / forbidden / none |
| Retention | raw JSON outside Git under retention `A4`; manifest/hash written immediately after every response |
| Health | no start, unreadable prior manifest, write failure or monitoring loss means `STOP_RUN`; no silent restart |

The proposal must also name one human monitoring owner and the terminal receipt
path before it can become executable. It does not schedule anything: each slot
is an independent foreground invocation and the second slot is blocked until
the first slot's health and retention receipt are available.

## Exact safety semantics

The offline validator must reject a packet if it attempts to use a credential,
adds a fallback or retry, permits more than eight reads, uses anything other
than two slots and the four declared offsets, marks a candidate provider as
selected, or changes any non-claim into a claim. It must also reject a plan
where raw retention or monitoring is optional, where a later slot can start
without the prior manifest, or where a capture-health failure is classed as a
market gap.

The future live result can be only:

- `SHAKEDOWN_PASSED_TECHNICAL_ONLY` — both slots have retained observations
  and no health failure;
- `SHAKEDOWN_FAILED_ROUTE` — route semantics or a retained response
  contradicts the exact packet;
- `SHAKEDOWN_INCONCLUSIVE` — a typed gap or any capture-health failure.

None authorises a 24-hour capture. Only the first permits a new owner gate to
consider one.

## Scope

Create a task/contract, machine-readable packet, schema, pure validator,
synthetic fixture, Russian readout, acceptance receipt and Catalog links.
Tests exercise the real validator and reject unsafe mutations. No provider
request, key, raw write, scheduler, database, dependency, wallet, transaction,
R2/R3 access, trial or numeric NetReturn enters the atom.

## Acceptance

- The packet is deterministic, schema-valid and bound to A10/A11A plus the
  frozen H07/H01 group.
- A missing explicit owner approval is not executable authority.
- The test matrix rejects provider promotion, count/offset drift, retry,
  fallback, optional retention, monitoring loss and unsafe second-slot start.
- The Russian readout explains the proposed eight-read ceiling and exact next
  owner decision without suggesting that data have already been collected.
- Catalog entries identify the packet as an offline control artifact with
  `TASK-30` and `FACTORY-001` consumers.
