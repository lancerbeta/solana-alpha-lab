# Owner readout — OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_V1

## Outcome

Jupiter ObservationSchedule transport now has an explicit response-body byte
budget and a bounded JSON parse. An unexpectedly huge, chunked, or
CPU-expensive provider body cannot grow into multi-GB resident memory or hold
the GIL through the 120s lease. Oversize and invalid JSON become typed
missingness; the call ledger exits `STARTED` on the ordinary handled path.

The V1 thread wall remains a waiter-side timeout for I/O that releases the
GIL. It is not a GIL-preempting hard kill. Bounded body + bounded parse is
the starvation control for the live large-body/CPU class.

## What changed

- `observation_provider_bounded_response.py`: `MAX_RESPONSE_BYTES = 2_000_000`
  (same-family 2 MiB transport cap; official `/recent` default ~30 mints;
  in-repo envelopes ~1–125 KiB, ≥16× headroom). Content-Length is early
  reject only; streamed byte counter is authoritative (`read(n)` + `MAX+1`
  sentinel). JSON number tokens longer than 40 characters are typed invalid.
- Production `JupiterReadonlyOpener` never calls unbounded `response.read()`.
- Typed outcomes: `RESPONSE_BODY_TOO_LARGE`, `RESPONSE_JSON_INVALID`, existing
  `TIMEOUT` / HTTP classes. `missing_reason` is the scientific type;
  `http_class=TRANSPORT` on oversize/invalid is fail-closed availability.
- Wall-deadline copy no longer claims a hard GIL kill.
- Zero-network proofs: Content-Length, chunked/unknown-length, malformed JSON,
  huge-int-in-container, near-ceiling parse headroom vs lease, STARTED exit,
  crash-sim remains fail-closed, secret non-leak, memory bound.

## Non-claims

- No VPS deploy / live commissioning in this atom
- No provider route/credential change
- No retry/fallback widening
- No estimand/sampling change
- No `LEASE_SECONDS` increase as the repair
- No new service/daemon/package
- 2 MiB is not an official Jupiter maximum
- Size+token bounding is not a proof that every conceivable 2 MiB JSON is
  scheduler-safe on every host

## After merge (separate owner gate)

Deploy SHA = merge commit on `main`. Commissioning must show: tick no longer
reaches ~GB-scale RSS or ~lease-length CPU on `/tokens/v2/recent`; wall or
bounded reject produces typed missingness; `call_ledger` does not stick at
`STARTED`; no `LEASE_FENCED` from this class; source-poll/RDP resume.
