# TASK-30 Birdeye pair OHLCV pilot readiness boundary — design

## Purpose

TASK-30 needs a continuous, point-in-time admissible 96 × 15-minute public
price/volume panel before it can test H07/H01. `T30-A1` instead established a
correct fail-closed result: the retained GeckoTerminal response does not prove
its interval timestamp semantics. The next useful action is not a backtest,
provider integration, or a second attempt at the same data route. It is a
small offline readiness boundary for one future Birdeye pair-OHLCV proof call.

The consumer is a later exact owner authorization decision. The output says
whether a single credentialed Birdeye REST request can be specified without
guessing about its interval, pair identity, authentication, or downstream
meaning. It is not that request and does not create a data panel.

## Why a readiness boundary comes first

Official Birdeye documentation describes a pair-scoped historical OHLCV REST
surface with Unix `time_from` and `time_to`, an API key, and an optional
`padding` parameter. It does not, in the evidence available to this task,
unambiguously establish that its REST request enum accepts `15m`. A separate
Birdeye WebSocket page lists `15m`, but a real-time WebSocket contract cannot
prove a historical REST request enum. Nor is the existing GeckoTerminal pool
address yet proven to be a Birdeye pair identifier.

Sending a request with either assumption would convert a cheap proof-of-surface
into ambiguous provider experimentation. The selected design therefore stores
both gaps as explicit blockers and refuses all provider execution until they
are resolved under a new exact authority scope.

## Considered approaches

1. **Call Birdeye REST with `15m` now.** Rejected. The static REST evidence
   does not prove that parameter, and the pool-to-pair mapping is not bound.
2. **Use the WebSocket `15m` documentation as a substitute.** Rejected. It is
   a different, real-time surface and would violate the historical REST
   consumer boundary.
3. **Freeze a minimal readiness contract first.** Selected. It is offline,
   lets a future owner see exactly what must be proven, and avoids consuming a
   credential or producing misleading raw data.

## Design

The implementation creates one task-owned, deterministic readiness policy and
its contract, schema, synthetic fixture, evaluator, targeted test, acceptance
receipt, Catalog registration, and Factory Fit review. It carries the prior
`T30-A1` semantic guardrail forward without modifying it.

The evaluator must return only `NOT_READY_FOR_PROVIDER_PILOT` while either of
these two required conditions is unproven:

- `BIRDEYE_REST_15M_ENUM_PROVEN` — a dated, official historical REST source
  explicitly admits the requested `15m` interval;
- `BIRDEYE_PAIR_IDENTITY_PROVEN` — a bounded identity proof associates the
  exact requested pool with the exact Birdeye pair identifier.

Two further conditions are intentionally left for a later owner gate:

- `BIRDEYE_API_KEY_LOCAL_PRESENCE_ATTESTED`, checked only as a local boolean;
  the key itself is never read, displayed, logged, written, or committed;
- `OWNER_ONE_CALL_AUTHORITY_GRANTED`, stating the final URL parameter set,
  one-request cap, retention, and stop conditions.

The policy rejects a WebSocket citation as proof of the REST enum, an
unverified pair address, a credential value, any retry/fallback, and promotion
of a future successful HTTP response to continuous-panel, PIT, alpha, trial,
or execution truth. The exact future authorization remains unavailable until
every required proof has been independently recorded.

## Boundaries and non-claims

This atom is entirely offline. It permits tracked contract/test/Catalog work,
ordinary Git delivery, and public official documentation references already
used for the decision. It permits zero provider/API/RPC/WSS calls, credential
use, R2/R3 access, raw-data retention, dependency changes, wallet/signer/
transaction actions, cash spend, TASK-30 trial/acceptance, Project Sources
changes, numeric PnL, or NetReturn claims.

The future call, if ever separately authorized, must remain exactly one
credentialed historical REST GET with no retry or fallback. Its raw response
must stay outside Git under the existing A4 retention boundary. Even a complete
response would be evidence about a surface only; it could not itself close
`T30-A1` timestamp semantics or admit a research trial.

## Validation and completion

Synthetic tests must accept the fully unresolved readiness state and reject:

- an asserted REST `15m` enum without a qualifying proof;
- use of a WebSocket document as REST proof;
- a pool address treated as a pair ID without a mapping proof;
- any non-zero provider or credential action counter;
- credential material in a record;
- retries, fallbacks, raw data, continuous-panel, PIT, alpha, or trial claims.

This is a durable data-access and semantic safety boundary, so its Factory Fit
review is `FULL_REVIEW`. The Project Sources disposition is `NO_CHANGE`: no
canonical task status, accepted raw data, or release candidate changes here.

## Completion criterion

The atom is complete when the repository can deterministically represent
`NOT_READY_FOR_PROVIDER_PILOT`, explain the two exact evidence gaps to its
future owner, and reject every shortcut above. Completion does not grant
provider, credential, or research authority.
