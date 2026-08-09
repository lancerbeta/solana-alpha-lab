# TASK-30 Birdeye pair OHLCV pilot readiness contract v1

## Consumer and decision

The consumer is a future exact owner provider-authority gate. This contract
records whether a single historical Birdeye pair-OHLCV proof call can be
specified without guessing about the REST interval enum, pair identity, local
credential availability, or owner authority.

The only v1 decision is `NOT_READY_FOR_PROVIDER_PILOT`. It is an offline
readiness result, not a provider request, price panel, PIT dataset, research
trial, strategy, execution route, PnL, or NetReturn decision.

## Frozen evidence state

As of 2026-08-09, public Birdeye material documents a historical pair-OHLCV
REST surface with Unix `time_from`/`time_to`, API-key authentication, and an
optional `padding` parameter. The available REST evidence does not prove that
the historical REST request enum admits `15m`. A separate WebSocket document
mentions `15m`; that real-time surface is not admissible as proof of the REST
enum.

The public GeckoTerminal pool candidate
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` is not a Birdeye pair ID until
an independent exact identity proof binds them. No Birdeye pair ID, API key,
or request URL is present in this atom.

## Required prerequisites for a later owner gate

All four states are deliberately frozen here and must remain unresolved:

| Prerequisite | Current state | Why it matters |
| --- | --- | --- |
| Historical REST `15m` enum | `UNPROVEN` | Prevents an unsupported or ambiguous request parameter. |
| Exact Birdeye pair identity | `UNPROVEN` | Prevents querying a different market under the same pool narrative. |
| Local key-presence attestation | `UNATTESTED` | Avoids assuming account access or exposing a credential. |
| One-call owner authority | `NOT_GRANTED` | Keeps provider execution outside this offline task. |

No field may convert any state to ready. A later atom must independently bind
the first two proofs, attest only a boolean for local key presence, and obtain
a new exact owner authorization before a call is technically eligible.

## Authority and non-claims

This atom permits only tracked offline contract, test, evidence, Catalog, and
ordinary Git delivery work. It authorizes zero provider/API/RPC/WSS calls,
credential use, raw-data writes, R2/R3 reads, dependency changes,
wallet/signer/transaction actions, cash spend, TASK-30 trial/acceptance, or
Project Sources changes.

No retry, fallback provider, request construction, raw-data path,
continuous-panel, PIT-admissibility, alpha, trial, execution, fill,
settlement, PnL, or numeric NetReturn claim is allowed. A credential field or
credential-like key is rejected even when its value is a test placeholder.

## Acceptance

Acceptance requires a closed JSON Schema, synthetic golden fixture,
deterministic evaluator, and adversarial rejections for REST/WebSocket
conflation, pair-identity promotion, all authority widening, credential
material, retry/fallback, raw data, source disposition drift, and research
promotions. It also requires hash-bound evidence, `FULL_REVIEW` Factory Fit,
Catalog registration, and `NO_CHANGE` for Project Sources.
