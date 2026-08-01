---
contract_id: CONTRACT-T21-R3-EVENT-TRIGGERED-SOURCE-P0-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A6S_R3_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1
status: FROZEN_FOR_SEPARATE_EXACT_PROVIDER_AUTHORITY
as_of: 2026-08-01
contains_secrets: false
---

# TASK-21 R3 source and P0 capture contract

## Purpose

Acquire the third and final independent outcome-blind nomination observation,
admit at most two previously unseen structurally valid Solana mints, and record
one executable Jupiter quote panel (`P0`) per admitted member. A complete R3
can bring the frozen final cohort to five new members across three independent
nomination batches; it does not evaluate alpha or authorize a trade.

## Selection integrity

R3 may use source lineage, mint identity, initialized Mint header,
token-program owner, decimals, observation/availability time and the immutable
six-mint prior-seen set. It must not read R2 quote, route, cost, rank, score,
price, volume, liquidity, PnL or hypothesis outcome values for selection.

The source sequence is exactly one keyless Dexscreener latest-token-profiles
request followed, only when mint identities exist, by one Solana public RPC
`getMultipleAccounts` request. The new observation must differ from R2 by ID
and content hash, be later than R2, and contain at least one unseen eligible
mint. Otherwise evidence is retained and execution stops without admission or
Jupiter calls. Admission is persisted before the first quote request.

## Bounded envelope

- source calls: Dexscreener `<=1`, Solana public RPC `<=1`;
- P0 calls: keyless Jupiter `<=8` per member and `<=16` total;
- nominations/admissions: `<=2`; retries `0`; concurrency `1`;
- create-only local durable bytes `<=16 MiB`;
- R3 P1/P2 reserves 32 further quote calls; full-plan projection remains
  `184/192` external, `8/8` source and `176/184` quote requests;
- current recovery, disk, response, storage and dataset caps fail closed.

Drive, credentials, cash, scheduler/deploy, Catalog/Project Sources mutation,
wallet, signer, transaction, destructive action, force/history rewrite and
merge remain zero.

## Acceptance and next boundary

PASS requires exact protected hashes, healthy recovery at start, create-only
source/admission/P0 evidence, deterministic population, exact read-back and
complete P0 for every admitted member. A provider or novelty stop retains the
precise evidence and does not retry or silently replace a member.

Completion makes R3 P1 eligible only after each P0 completion plus 1,801
seconds and separate authority. It grants no TASK-22, A7, trading or merge
authority.
