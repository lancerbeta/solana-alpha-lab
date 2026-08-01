---
contract_id: CONTRACT-T21-R2-EVENT-TRIGGERED-SOURCE-P0-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A6S_R2_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1
status: FROZEN_FOR_EXACT_USER_AUTHORIZED_EXECUTION
as_of: 2026-08-01
contains_secrets: false
---

# TASK-21 R2 source and P0 capture contract

## Purpose

Acquire one independent, outcome-blind R2 nomination observation, admit at most
three previously unseen structurally valid Solana mints, and immediately record
one executable Jupiter quote panel (`P0`) per admitted member. This extends the
bounded forward cohort; it does not evaluate alpha or authorize a trade.

## Frozen selection boundary

The source sequence is exactly one keyless Dexscreener latest-token-profiles
request followed, only when mint identities exist, by one Solana public RPC
`getMultipleAccounts` request. Selection may use only chain identity, mint
identity, initialized Mint header, token-program owner, decimals, observation
and availability time, prior seen-mint membership, and immutable source hashes.

Price, volume, liquidity, paid status, rank, score, route, quote result, cost
bps, PnL, hypothesis outcome, and any later panel result are forbidden inputs.
The admission decision is persisted before the first Jupiter request.

The source observation must have a new ID and content hash, be observed strictly
after R1, and contain at least one previously unseen eligible mint. Otherwise its
create-only evidence is retained and the atom stops without an admission or
Jupiter request.

## Physical envelope

- source calls: Dexscreener `<=1`, Solana public RPC `<=1`;
- P0 calls: keyless Jupiter quote `<=8` per member and `<=24` total;
- nominations and admissions: `<=3`;
- retries `0`, concurrency `1`, foreground only;
- create-only local durable bytes `<=16 MiB`;
- whole-TASK-21 request, response, storage, dataset, recovery, and disk caps are
  revalidated before execution and reconciled after read-back;
- partial provider failure retains explicit evidence and stops without retry or
  silent replacement.

Drive, credentials, cash spend, scheduler/deploy, Catalog or Project Sources
mutation, wallet, signer, transaction, destructive action, force push, merge,
and historical rewrite are zero.

## Acceptance

PASS requires exact protected-input hashes, healthy recovery at start, a
create-only source partition, deterministic nomination/admission receipts, an
exact inventory and hashes, and either:

1. all admitted P0 panels complete within caps; or
2. a truthful stopped receipt preserving the precise stop reason and all
   evidence produced before it.

Completion schedules each admitted member's P1 as event-triggered foreground,
not before its P0 completion plus 1,801 seconds. It grants no external authority
for P1, TASK-22, A7, or any trading action.
