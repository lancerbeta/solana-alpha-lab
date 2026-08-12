# Provider Route Capability Registry V1 — design

Date: 2026-08-13
Scope: bounded TASK-30 control patch
Decision: `PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1`

## Problem

The repository preserves task-specific provider contracts and exact runtime
receipts, but it has no compact current index answering a simpler operational
question: *which local transport has actually reached a given public/provider
route, what failed, and what must be checked before spending an authorized
attempt?*

This gap has now caused repeated route-discovery cost. In the POPCAT pilot,
Windows `HttpClient` and `curl` failed before HTTP at the local TLS layer, while
the bundled Node.js TLS client reached the same keyless DexScreener family and
returned HTTP 200. A later Helius call through Node.js reached a different
terminal state, `ECONNRESET`, before an RPC result. These are transport facts,
not market facts and not provider-wide availability claims.

The existing roadmap trigger for a research tool capability registry has
therefore fired: a second real route and repeated selection cost now exist.

## Decision and alternatives

Create one declarative YAML registry, a closed JSON Schema, one small validator,
one focused test surface, and Catalog bindings.

Rejected alternatives:

- adding prose only to `AGENTS.md`: easy to encounter but not structured,
  hash-bound or mechanically validated;
- creating a generic provider router/service: premature automation, new runtime
  behavior and a larger failure surface before route evidence is stable;
- recording only task receipts: preserves history but forces every future task
  to rediscover the current usable route by searching unrelated evidence.

The registry is navigation and operational memory. It does not execute calls,
select providers automatically, retry, fall back, read credentials or grant
authority.

## Artifacts

The bounded implementation adds:

- `configs/provider_route_capability_registry_v1.yaml` — current route entries;
- `catalog/schemas/provider_route_capability_registry.schema.json` — closed
  structural contract;
- `src/solana_alpha_lab/provider_route_capability_registry.py` — deterministic
  loader/validator and lookup by stable route ID;
- `tests/test_provider_route_capability_registry.py` — positive and adversarial
  validation;
- one sanitized TASK-30 acceptance receipt;
- Catalog records and generated navigation updates.

No dependency, scheduler, service, database, connector, provider call or Project
Source role is added.

## Registry model

The root contains an exact schema/version, update policy and a non-empty list of
closed route records. Every route has a stable `route_id` and records:

- provider/source and endpoint family;
- access class: keyless or local environment credential;
- operation and transport protocol;
- the local client/runtime that was actually observed;
- preflight steps that do not consume a credentialed attempt;
- last observed UTC time and terminal class;
- evidence pointer and response hash when response bytes exist;
- known failure fingerprints and their layer;
- retry/fallback policy;
- explicit non-claims.

V1 starts with two records:

1. DexScreener Solana token-pairs, keyless HTTPS, successfully observed through
   bundled Node.js TLS with HTTP 200. Windows Schannel failures are retained as
   local transport failures, not provider failures.
2. Helius standard Solana RPC `getSignaturesForAddress`, environment credential,
   Node.js HTTPS, most recently terminated by `ECONNRESET` before an RPC result.
   This record cannot be labelled usable merely because TLS succeeded for a
   different host or because another historical Helius attempt succeeded.

Secrets, raw response bodies, query strings carrying credentials and absolute
user paths are forbidden in tracked entries.

## Update and encounter rules

The registry is updated only from a named observed receipt or official contract
change. A failed observation may update the terminal state without deleting a
prior success; history remains in immutable receipts. `last_success` and
`last_observation` are distinct, so one outage cannot erase known capability and
one old success cannot hide current failure.

Future Entry/Reuse gates must consult the registry before building or invoking a
provider transport. This is enforced by a short pointer in the existing task
startup/reuse policy, not by duplicating route data in `AGENTS.md`.

When no matching route exists, the result is `REGISTRY_GAP`, not proof that the
source is unavailable. When a record is stale, the caller must use the declared
preflight or request a new bounded authority gate; it must not silently retry or
fall back.

## Validation and acceptance

Deterministic tests require:

- unique stable route IDs and exact closed keys;
- UTC timestamps and SHA-256 syntax;
- a response hash only when response bytes were observed;
- credentialed routes to name environment-only secret handling;
- no secret-shaped keys/values, URLs with credentials or absolute local paths;
- distinct `last_success` and `last_observation` semantics;
- typed local transport failure distinct from provider/data/market outcomes;
- `retry=false`, `fallback=false`, `authority_granted=false` in every V1 entry;
- lookup of DexScreener and Helius by stable ID;
- Catalog hashes and generated navigation consistency.

Acceptance is `REGISTRY_VALIDATED_NO_RUNTIME_AUTHORITY`. It does not make either
provider reliable, approve a future call, establish data completeness, create a
TASK-30 trial, or support alpha/PnL/NetReturn/cashflow claims.

## Rollback and future trigger

Rollback is deletion of the new registry assets and Catalog transaction before
downstream adoption; no external state must be undone.

Automatic provider routing remains WATCH-only. Its activation trigger is at
least two consumers repeatedly selecting routes from this registry with a
measured manual cost or a requirement for unattended recovery. Until then,
lookup stays deterministic and human/agent-directed.
