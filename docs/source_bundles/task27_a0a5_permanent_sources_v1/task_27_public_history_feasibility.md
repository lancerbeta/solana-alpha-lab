---
task_id: TASK-27
semantic_version: "1.0"
status: SOURCE_RECONCILIATION_CANDIDATE_UI_ACTIVATION_PENDING
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

## Delivered offline foundation

- `T27-A0-A2_HISTORICAL_PRICE_VOLUME_CONTRACT_V1` defines the 15-minute
  pool-interval record, identity/time fields, forward-label `UNKNOWN` rules and
  no-execution boundary.
- `T27-A0-A3_HISTORICAL_COLLECTION_AUTHORITY_CONTRACT_V1` defines a future
  bounded collection authority and rejects silent provider fallback, incomplete
  panels and claims beyond history feasibility.
- `T27-A0-A4_BOUNDED_PUBLIC_HISTORY_FEASIBILITY_AUTHORITY_PACKET_V1` binds a
  candidate public source, future caps, selection snapshot, raw manifest,
  availability distinction and source-smoke prerequisite.
- `T27-A0-A5_PERMANENT_SOURCES_RECONCILIATION_AND_SMOKE_V1` prepares this
  candidate Source set. It has not replaced Project Sources in UI.

## Current status

`VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING`.

PR #48 merged the A4 packet into main at
`082f3f8184e84c31c876a484cf8e876a40691f62`; GitHub push CI run `31224401848`
is successful. Repository delivery does not activate Project Sources and does
not declare TASK-27 complete.

## Exact next boundary

The owner replaces the five mutable Project Source roles, keeps Operating
System v8.5 and Blueprint v2.3 unchanged, and returns a seven-role smoke.
Only `ACTIVATION_CONFIRMED_USER_SMOKE` may clear A4's source-alignment
prerequisite. After that, an exact owner external-read review remains required
before any provider GET.

## Hard limits and non-claims

`provider_read_authority=false`; provider/API/RPC/WSS calls, credentials,
raw-history retention, R2/R3 reads, wallet, signer, transaction, funding,
cash spend, deployment and strategy promotion are not authorized.

Even a future capture may not claim a representative universe, PIT admissible
history without availability proof, quote/fill/execution, PnL, NetReturn or
cashflow. Missing stays `UNKNOWN`; it never means zero, flat, settled or a
continuous observed path.

## Definition of done for this source atom

This atom is technically ready only when the replacement candidate is
validated, delivered by PR and its UI instruction is explicit. It becomes
active only after the user performs the bounded UI replacement and returns the
smoke receipt. TASK-27 itself remains open after either event.
