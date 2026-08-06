---
contract_id: CANARY-SPECIFICATION-ONLY-CONTRACT-001
contract_version: "1.0"
task_id: CANARY_SPECIFICATION_ONLY_V1
as_of: "2026-08-06"
scope: OFFLINE_ONLY
---

# Canary specification-only contract v1

## Contract

CANARY_SPECIFICATION_ONLY_V1 produces a versioned draft specification for one
possible technical micro-canary. It is an input-preparation boundary, not an
execution route. OWNER_AUTHORITY_PACKET_BINDING_V1 remains the sole safety
truth owner and evaluator for owner-packet completeness.

The only legal state is DRAFT_OWNER_INPUT_REQUIRED. The frozen flow shape is
SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT; the all-in cash-at-risk cap is
exactly 300 USD cents. No tracked file may contain a real wallet address,
verification hash, token, program, route, quote, signature, endpoint or owner
approval phrase.

## Required owner input names

1. token
2. program
3. route
4. wallet_public_address
5. proposed_notional_usd_cents
6. maximum_separate_fees_usd_cents
7. quote_basis
8. expires_at
9. monitoring_reference
10. reconciliation_reference
11. stop_and_recovery_procedure
12. exact_owner_approval_phrase

The values are OWNER_INPUT_REQUIRED; technical wallet identity is
OWNER_LOCAL_ONLY and remains in an ignored owner-controlled location.

## Prohibitions and failure semantics

canary_authority=false, task27_authority=false, execution action is NONE, and
numeric NetReturn is forbidden. A non-draft state, a cap other than 300 cents,
a missing owner-input name, true authority, any provider count above zero, or
material wallet/endpoint text is rejected. These rejections do not silently
convert missing or unknown execution truth into a zero value.

## Authority boundary

This contract does not authorize wallet creation/connection, signer
activation, provider/API/RPC/WSS access, quote retrieval, transaction
build/simulate/sign/send, cash spend, R3 access, TASK-27 or strategy
promotion. Any such action requires a separate exact owner decision.
