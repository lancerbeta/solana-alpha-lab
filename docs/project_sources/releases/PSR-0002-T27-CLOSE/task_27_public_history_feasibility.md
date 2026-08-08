---
task_id: TASK-27
semantic_version: "1.1"
status: TECHNICALLY_RECONCILED_SOURCE_ACTIVATION_PENDING
as_of: "2026-08-08"
depends_on: [TASK-26C, OWNER_AUTHORITY_PACKET_BINDING_V1]
contains_secrets: false
---

# TASK-27 — Bounded public historical price/volume feasibility

## Purpose

TASK-27 asks a narrow prior question: can one bounded public Solana pool
price/volume history route ever produce enough correctly identified,
time-qualified, retained evidence to justify later research? It does not test
an alpha, quote, fill, execution route, PnL, NetReturn or owner cashflow.

## Delivered evidence and terminal reconciliation

- `T27-A0-A2_HISTORICAL_PRICE_VOLUME_CONTRACT_V1` defines the 15-minute
  pool-interval record, identity/time fields, forward-label `UNKNOWN` rules and
  no-execution boundary.
- `T27-A0-A3_HISTORICAL_COLLECTION_AUTHORITY_CONTRACT_V1` defines a future
  bounded collection authority and rejects silent provider fallback, incomplete
  panels and claims beyond history feasibility.
- `T27-A0-A4_BOUNDED_PUBLIC_HISTORY_FEASIBILITY_AUTHORITY_PACKET_V1` binds a
  candidate public source, future caps, selection snapshot, raw manifest,
  availability distinction and source-smoke prerequisite.
- `T27-A0-A5_PERMANENT_SOURCES_RECONCILIATION_AND_SMOKE_V1` established the
  prior seven-role Source release and owner smoke protocol.
- `T27-A1_STAGE_A_PUBLIC_PAIR_IDENTITY_READ_V1` confirmed the named Solana
  pool identity without testing alpha, execution or cashflow.
- `T27-A1S2_STAGE_B_SOLANA_TRACKER_POOL_HISTORY_PILOT_V1` produced 33 of 96
  required natural 15-minute bars; 63 bars remain `MISSING_UNKNOWN`.
- `T27-A1S3` kept that result route-specific, and `T27-A1S4` binds the
  accepted route close with `NO_NEW_PROVIDER_READ`.
- `T27-A2_TERMINAL_RECONCILIATION_AND_SOURCES_RELEASE_CANDIDATE_V1` records
  `NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE` and
  prepares PSR-0002. It does not activate Project Sources in UI.

## Current status

`TECHNICALLY_RECONCILED_SOURCE_ACTIVATION_PENDING`.

TASK-27's permitted conclusion is only that the named authorised route did not
demonstrate a feasible history panel within its frozen scope. It does not say
that all public history is infeasible. Repository delivery and exact CI
read-back remain stronger implementation truth than this candidate; UI
activation and final owner-visible completion are still pending.

## Exact next boundary

The owner replaces the five mutable Project Source roles, keeps Operating
System v8.5 and Blueprint v2.3 unchanged, and returns a seven-role smoke.
Only that `ACTIVATION_CONFIRMED_USER_SMOKE` can activate PSR-0002. It does not
reopen the closed route or grant a provider GET.

## Hard limits and non-claims

`provider_read_authority=false`; provider/API/RPC/WSS calls, credentials,
raw-history retention, R2/R3 reads, wallet, signer, transaction, funding,
cash spend, deployment and strategy promotion are not authorized.

TASK-27 does not claim a representative universe, PIT-admissible history,
quote/fill/execution, PnL, NetReturn or cashflow. Missing stays `UNKNOWN`; it
never means zero, flat, settled or a continuous observed path. No next task is
selected by this terminal result.

## Definition of done for this source atom

This task is technically reconciled when the A2 candidate is validated,
delivered by PR and exact CI is read back. It becomes Source-active only after
the user performs the bounded UI replacement and returns the smoke receipt.
That later receipt completes the Project Sources activation only; it creates no
provider, execution or cash authority.
