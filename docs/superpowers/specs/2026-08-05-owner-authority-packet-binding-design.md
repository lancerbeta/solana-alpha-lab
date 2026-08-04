---
title: Owner Authority Packet Binding v1 — approved design
status: DESIGN_APPROVED_PENDING_USER_SPEC_REVIEW
candidate_task_id: OWNER_AUTHORITY_PACKET_BINDING_V1
as_of: 2026-08-05
classification: EPHEMERAL_DESIGN_ARTIFACT_NOT_A_CANARY_AUTHORIZATION
catalog_impact: NONE_UNTIL_IMPLEMENTATION_ARTIFACTS_EXIST
contains_secrets: false
external_actions: 0
wallet_signer_transaction_actions: 0
cash_spend_usd_cents: 0
---

# Owner Authority Packet Binding v1 — design

## Decision this design supports

The goal owner may later decide whether one bounded technical DEX canary is
specified precisely enough to review. This document does not grant that
authority, create a wallet, connect a signer, obtain a quote, build a
transaction, spend money, or begin TASK-27.

## Agreed future canary shape

The future technical canary is a two-leg, owner-operated round trip:

```text
SOL -> one exact memecoin -> SOL
```

The second leg is an immediate exit for execution verification, not a trading
hold. It may begin only after the first leg is terminally observed and its
token/SOL inventory has been reconciled. An `UNKNOWN`, failed reconciliation,
unexpected balance delta, monitoring loss, route mismatch, or cap breach stops
the sequence; it never causes an automatic retry or an improvised exit.

The owner-selected all-in cash-at-risk cap is **USD 3.00**. At future execution
time this cap must include input notional, network fees, relay or priority fees,
ATA rent, and every other separately charged amount. If a fresh, recorded
preflight cannot prove the proposed sequence is within the cap, the canary is
rejected before the first send.

## Chosen approach

Use a manually created, dedicated technical wallet only after a separately
approved owner packet. The owner controls it through an ordinary wallet
application and manually confirms any later action. It must not be the owner's
main asset-holding wallet, and its seed phrase or private key must never enter
chat, repository, logs, URLs, or project files.

This is deliberately narrower than an automated isolated signer. Automation
would add a new key-handling and deployment boundary before the project has
even observed one reconciled route. A main wallet is rejected because it mixes
the bounded canary with unrelated assets and risk.

## Packet contract to implement after this design review

The future offline binding artifact must have two states.

1. `DRAFT_OWNER_INPUT_REQUIRED`
   - Records the agreed flow, immediate-exit rule, and USD 3.00 proposed cap.
   - Keeps `token`, `program`, `route`, wallet public address, exact notional,
     maximum separate fees, quote basis, expiry, and stop/recovery procedure as
     explicit `OWNER_INPUT_REQUIRED` values.
   - Is never executable and must be rejected by the validator as authority.

2. `READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION`
   - Exists only when every required field is bound to one canary ID.
   - Contains the exact action, token mint, program, route, proposed notional,
     all-in cap, maximum separately charged fees, expected inventories before
     and after each leg, monitoring/reconciliation references, expiry, and the
     exact owner approval phrase.
   - Remains a review packet. A separate explicit approval is still required
     before any wallet creation, funding, quote request, signer use,
     transaction, provider call, or cash action.

Missing values are not defaults. They must remain visible as
`OWNER_INPUT_REQUIRED`; a validator must reject missing, zero-substituted, or
ambiguous fields.

## Future execution sequence — not authorized by this design

1. Re-run a fresh Entry Gate for the exact token/program/route and current
   execution conditions.
2. Bind the final packet and obtain the owner's exact one-time approval.
3. The owner creates and funds a dedicated wallet outside this project, within
   the approved cap, without disclosing secret material.
4. Perform the first leg only if health, monitoring, quote freshness, allowlist,
   and cap checks pass.
5. Reconcile the first leg. `UNKNOWN` blocks retry and the planned exit until
   reconciliation resolves the actual inventory and fees.
6. Perform the immediate exit only when the first leg is reconciled and every
   health/cap/inventory rule still passes.
7. Reconcile the full round trip and retain the witness. Only then can a new
   Entry Gate assess whether TASK-27 is admissible.

## Proposed bounded implementation

After user review of this design, implement only an offline binding contract,
schema, synthetic fixture, deterministic validator, adversarial tests, and
Catalog transaction. The validator will cover at least:

- a draft with intentionally missing owner inputs;
- a complete packet that remains non-executable;
- USD 3.00 cap and separate-fee accounting requirements;
- no token/program/route substitution;
- immediate-exit only after first-leg reconciliation;
- block on `UNKNOWN`, monitoring loss, inventory mismatch, route mismatch, or
  cap breach;
- no wallet, seed, private key, signed bytes, provider/API/RPC/WSS call, or
  transaction path.

No generic execution platform, provider adapter, wallet connector, signer,
price feed, deployment, or strategy logic is in scope.

## Definition of done for the later implementation task

The offline packet has a versioned contract and schema; deterministic tests
prove that incomplete or unsafe packets cannot appear ready; Catalog and
generated consumers describe the new assets; and acceptance evidence records
zero external, wallet, signer, transaction, and cash side effects. The result
must retain `TASK-27_authority=false`.

## Review checklist

- The USD 3.00 cap is a ceiling, not a permission to spend.
- The round trip is execution verification, not an alpha trade.
- The dedicated technical wallet is a future user-only action, not an output
  of this task.
- Every unknown is explicit and fail-closed.
- No wording grants canary or TASK-27 authority.
