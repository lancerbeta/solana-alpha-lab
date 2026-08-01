---
contract_id: CONTRACT-T21-R2-P2-EVENT-TRIGGERED-CAPTURE-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A6S_R2_P2_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1
status: LOCAL_RUNTIME_PREP_COMPLETE_EXTERNAL_AUTHORITY_REQUIRED
as_of: 2026-08-01
contains_secrets: false
---

# TASK-21 R2 P2 event-triggered foreground capture

## Outcome

Capture the final executable quote panel for the exact three outcome-blind R2
members. P2 closes the three-panel path for this batch; it does not reselect
tokens, score outcomes, evaluate alpha, admit R3, or trade.

## Time and population invariants

Each member becomes eligible only after its accepted P1 completion plus 1,801
seconds. All three must be eligible before the first P2 provider call. There is
no narrow expiry window, but every P2 must remain inside the member's 24-hour
total-span deadline from admission. A missed deadline is an explicit gap, never
a backfill or silent reschedule.

The population, order, mints, decimals, nominations, R2 P0/P1 acceptance,
admission bytes, and all three P1 receipts are hash-bound. P0 and P1 route,
price, cost, PnL, rank, or hypothesis outcome cannot alter membership.

## Reuse and evidence immutability

P2 reuses the already accepted quote projection, dependent-sell, create-only
write, cap, and evidence inventory primitives from the P1 implementation.
Accepted P1 files are not refactored or rewritten because their hashes are
decision-bearing evidence.

## Physical and authority boundary

The runtime is foreground-only, keyless Jupiter quote-only, four dependent
buy/sell pairs per member, at most eight calls per panel and 24 total. Retries
are zero and concurrency is one. Responses are bounded to 9 MiB total and
create-only local evidence to 16 MiB under the remaining whole-TASK-21 caps.

Live execution requires a separate exact user gate after a fresh time,
recovery, budget, disk, protected-input, and output-collision preflight. A
provider failure retains evidence and stops without retry or substitution.

Drive, nominations/admissions, credentials, cash, scheduler/deploy,
Catalog/Project Sources, wallet/signer/transactions, destructive actions,
force/history rewrite, and merge remain zero.

## Next boundary

Complete P2 closes R2 but does not invent or authorize the R3 source/P0 atom.
The control plane must review the frozen success gate, remaining two-member
need, source budget, and recovery before naming R3. P2 does not authorize
TASK-22, A7, dataset promotion, unsealing, or an alpha claim.
