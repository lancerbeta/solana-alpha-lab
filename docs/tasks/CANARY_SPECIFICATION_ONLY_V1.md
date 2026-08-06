---
task_id: CANARY_SPECIFICATION_ONLY_V1
task_version: "1.0"
status: IMPLEMENTATION_CANDIDATE
as_of: "2026-08-06"
scope: OFFLINE_ONLY
depends_on:
  - OWNER_AUTHORITY_PACKET_BINDING_V1
---

# CANARY_SPECIFICATION_ONLY_V1

## Purpose

This task records one bounded, future-facing micro-canary specification without
creating a wallet, requesting a quote, contacting a provider, building a
transaction, or spending cash. Its only consumer is the owner deciding whether
to prepare the local inputs for a later, separately authorized canary gate.

## Frozen specification

- State: "DRAFT_OWNER_INPUT_REQUIRED".
- Flow shape: "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT".
- Total cash-at-risk cap: 300 USD cents.
- Technical wallet alias, public address and verification hash:
  "OWNER_LOCAL_ONLY".
- Safety truth owner: "OWNER_AUTHORITY_PACKET_BINDING_V1".

The owner must supply, locally and outside tracked files, the names/values
required by the predecessor packet: token, program, route,
wallet_public_address, proposed_notional_usd_cents,
maximum_separate_fees_usd_cents, quote_basis, expires_at,
monitoring_reference, reconciliation_reference, stop_and_recovery_procedure
and exact_owner_approval_phrase.

## Explicit non-claims

- This is not an approval to create or connect a wallet.
- This is not an approval for provider/API/RPC/WSS access or a quote.
- This is not an approval to build, simulate, sign or send a transaction.
- This records no real owner value, route, token, program or endpoint.
- This creates no canary or TASK-27 authority and no numeric NetReturn.
- No cash, R3 value or dependency is used.

## Acceptance boundary

The artifact is valid only when its deterministic fixture rejects unsafe
state/cap/authority/input mutations and all side-effect counters are zero.
A later real canary requires a new owner decision and its own bounded gate.
