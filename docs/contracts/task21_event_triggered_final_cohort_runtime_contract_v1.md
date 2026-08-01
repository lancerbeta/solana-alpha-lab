# TASK-21 Event-Triggered Final Cohort Runtime Contract v1

## Purpose

Prepare the smallest reusable runtime boundary for the final TASK-21 cohort.
The runtime admits future candidates from two new content-distinct nomination
observations and plans three foreground panels per admitted member. It does not
collect, schedule, trade, or declare the dataset ready.

## Frozen scope

- Atom: `T21-A6S_EVENT_TRIGGERED_FINAL_COHORT_RUNTIME_PREP_V1`.
- Authority: `LOCAL_WRITE_ONLY` from the owner's exact gate phrase.
- Historical T1/H0/H1/H6/H24 artifacts and modules are immutable inputs.
- The information-sufficiency rebase remains the decision owner.
- The implementation is a forward-only adapter with no transport or writer.
- H72/H168 remain trigger-only and are not part of this runtime.

## Admission state machine

The accepted source sequence is `T21-R1` (existing), then `T21-R2`, then
`T21-R3`. R2 may evaluate at most three candidates and R3 at most two. Across
TASK-21 the exact evaluated-candidate cap remains eight: three already used plus
five available to this extension.

Before admission the runtime requires:

1. the expected batch identifier;
2. a new source-observation identifier;
3. a source-content SHA-256 not accepted before;
4. `observed_at` strictly after every accepted earlier batch;
5. deterministic candidate order by availability, observation, event ID, mint;
6. at least one policy-eligible mint not present in the prior seen-mint set;
7. zero TASK-21 quote, route, price, terminal, rank, PnL, return, or verdict
   input.

A repeated/non-novel observation is retained as evidence and stops without
admission. Ineligible and duplicate candidates retain explicit evaluated states.
No candidate is silently replaced and no automatic extension is possible.

Member identity is content-addressed from policy version, batch, nomination
event, and mint. Admission reserves the entire remaining three-panel call budget
for each member before returning success. Headroom is a safety margin, not new
authority.

## Foreground panel state machine

Each new member has ordered panels `P0 -> P1 -> P2`:

- P0 becomes eligible at admission.
- P1 and P2 become eligible only 1,801 seconds after the prior completed panel.
- All three must occur no later than 86,400 seconds after admission.
- There is no narrow grace window, background process, retry, concurrency, or
  backfill.
- A missed total span is retained as a gap and stops that member safely.
- Unhealthy recovery, an exact byte/storage/disk cap, or insufficient request
  budget also stops safely.

An eligible decision is only `READY_FOR_SEPARATE_EXTERNAL_AUTHORITY`. It is not
provider authority and performs no call. A future external atom must revalidate
the complete state and receive an exact owner gate.

## Exact bounds

- Whole TASK-21 request caps: 192 external, 8 source, 184 quote.
- Starting used counts: 60 external, 4 source, 56 quote.
- Maximum extension: 4 source plus 120 quote requests.
- Projected total: 184 external, 8 source, 176 quote; external headroom 8.
- Per panel: at most 8 provider calls, 4 quote pairs, zero retries.
- Success evidence: 5 complete new members, 15 panels, 60 quote pairs across
  three independent nomination batches including accepted R1.
- Success claim: narrow conditional analysis only; no market-wide or
  cross-regime generalization.

## Acceptance

Offline acceptance must prove the exact 3+2 happy path and adversarially reject
outcome leakage, bad order, duplicate content, early panels, expired spans,
unhealthy recovery, and physical-cap exhaustion. It must also prove deterministic
member IDs, full-budget reservation, zero external side effects, and the exact
next unauthorized boundary.

## Non-claims and next boundary

This atom does not nominate or admit a real token, capture a panel, write raw or
dataset data, use Drive, spend credits or cash, update Catalog/Sources, start
TASK-22, or finalize TASK-21.

Next boundary: `T21-A6S_R2_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1`, separately
authorized with exact provider/API/RPC/WSS and local durable-write limits.
