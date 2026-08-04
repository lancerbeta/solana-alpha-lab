# TASK-26B minimal execution-witness route contract v1

## Atom

`T26B-A1_FREEZE_MINIMAL_EXECUTION_WITNESS_ROUTE_V1`

## Purpose

Freeze the cheapest execution-evidence route decision after testing historical
and cache-first options against the TASK-26A gap surface, and specify a future
owned witness without creating execution authority.

## Routes

Historical/cache-first is evaluated first:

1. `HISTORICAL_THIRD_PARTY_CHAIN`
2. `QUOTE_ONLY`
3. `BUILD_SIMULATION`
4. `OWNED_INSTRUMENTED_CANARY`

## Evidence classes

- `FEE_CHARGEABILITY`
- `SEND_ATTEMPT`
- `LANDING`
- `FILL`
- `INVENTORY`
- `SETTLEMENT`

## Semantics

- Quote does not prove attempt, landing, fill, or settlement.
- Build/simulation does not prove actual landing or cashflow.
- Historical third-party transactions may support observed processed/landing
  state, chain fees, and token deltas for selected transactions only.
- Historical third-party transactions do not prove rejected/dropped attempt
  denominators, retry intent, owner inventory, or owner settlement.
- Missing or `UNKNOWN` never becomes zero, false, flat, or settled.

## Decision vocabulary

Exactly one of `HISTORICAL_RECONSTRUCTION_SUFFICIENT`,
`OWNED_CANARY_REQUIRED`, `REDESIGN_ESTIMAND`, or `PAUSE`.

When TASK-26A facts remain 36/35/1 with five required classes complete for
0/36 pairs, the expected decision is `OWNED_CANARY_REQUIRED` with
`canary_authority=false`.

## Future owned witness (spec only)

Must record stable attempt/retry identity, quote/build context,
submitted/terminal timestamps, terminal state, signature, processed state,
token and SOL deltas, separately charged fees, inventory before/after,
settlement basis, reconciliation reference, source hashes, and UNKNOWN
recovery path.

Future launch requires a separate exact gate: threat model, isolated signer,
explicit wallet boundary, exact cash cap, program/route allowlist, manual owner
approval, reconciliation-before-retry, kill switch, and no strategy logic.

This atom creates no wallet, signer, transaction builder, send path, or
deployment.
