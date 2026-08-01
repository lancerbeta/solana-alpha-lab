---
contract_id: CONTRACT-T21-R3-P1-EVENT-TRIGGERED-CAPTURE-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A6S_R3_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1
status: LOCAL_RUNTIME_PREP_COMPLETE_EXTERNAL_AUTHORITY_REQUIRED
as_of: 2026-08-01
contains_secrets: false
---

# TASK-21 R3 P1 event-triggered foreground capture

## Outcome

Capture the second executable quote panel for the exact two outcome-blind R3
members. P1 measures another point on the same frozen execution-capacity path;
it does not reselect tokens, score outcomes, evaluate alpha, or trade.

## Time and population invariants

Each member becomes eligible only after its accepted P0 completion plus 1,801
seconds. Both must be eligible before the first P1 provider call. There is no
narrow expiry window, but each P1 must remain inside the member's 24-hour total
span from admission. A missed deadline is an explicit gap, never a backfill.

The population, order, mints, decimals, nomination identities, R3 acceptance,
admission-event bytes, and both P0 receipts are hash-bound. Quote, route, price,
cost, PnL, rank, or hypothesis outcome cannot alter membership.

## Physical and authority boundary

The runtime is foreground-only, keyless Jupiter quote-only, four dependent
buy/sell pairs per member, at most eight calls per panel and 16 total. Retries
are zero and concurrency is one. Responses are bounded to 9 MiB total and
create-only local evidence to 16 MiB under the remaining whole-TASK-21 caps.

Live execution requires exact user authority plus a fresh time, recovery,
budget, disk, protected-input, and output-collision preflight. A provider
failure retains evidence and stops without retry or member substitution.

Drive, nominations/admissions, credentials, cash, scheduler/deploy,
Catalog/Project Sources, wallet/signer/transactions, destructive actions,
force/history rewrite, and merge remain zero.

## Next boundary

Complete P1 makes each member's P2 eligible only after that member's P1
completion plus 1,801 seconds. P2 has no authority until its own exact gate.
Neither P1 nor P2 alone authorizes TASK-22, A7, dataset promotion, or alpha.
