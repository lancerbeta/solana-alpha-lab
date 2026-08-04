# TASK-26C — Minimal owned execution canary readiness and authority gate

## Status boundary

This task prepares one future, owner-operated and instrumented technical canary.
It is an offline readiness gate, not a canary launch. Canonical acceptance and any
future authority remain owned by the Work/Codex control plane and the goal owner.

## Objective

Turn the TASK-26B decision `OWNED_CANARY_REQUIRED` into a minimal, deterministic
package that can be audited before the owner considers one technical canary. The
package must preserve the distinction between an attempted transaction, its
terminal chain observation, reconciled inventory, and settlement.

## Scope

- one synthetic witness contract and reconciliation-before-retry state machine;
- one allowlist policy that is deny-by-default until owner input is bound;
- one manual owner-approval packet template;
- deterministic fake signer and transport test doubles only;
- threat, health, fee-cap, inventory and monitoring reject paths.

## Hard non-claims

- No wallet, signer, transaction, signed bytes, simulation, provider/API/RPC/WSS
  execution, funding, cash spend, deployment, R3 access, numeric NetReturn or
  TASK-27 work.
- `READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS` is a readiness result. It
  never grants authority or authorizes a future canary.
- This task does not migrate `schemas/schema_v1.sql` or create a production
  execution platform. Its contract identifies a future migration decision only.

## Owner decision and consumer

The owner can decide whether the future authority packet is sufficiently explicit
to review. The direct consumer is the next separately authorized owned-canary
decision; TASK-27 remains blocked until complete evidence or an explicitly
redesigned estimand exists.

## Definition of Done

The versioned contract, JSON Schema, deterministic fixture, offline engine,
adversarial tests, Catalog transaction and Full Factory Fit review agree on one
of the task decision enums. `UNKNOWN` must block retry and new action until
reconciliation, and every excluded-action counter must remain zero.
