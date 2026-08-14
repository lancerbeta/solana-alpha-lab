---
protocol_id: DELIVERY_HARNESS_PROTOCOL_V1
status: ACTIVE_IMPLEMENTATION_CANDIDATE
as_of: '2026-08-14'
harness_id: DELIVERY_HARNESS_V1
---

# Delivery Harness Protocol

## Exact workflow

`CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH -> EXACT MERGE GATE -> READ-BACK`

### Check and context

Run the deterministic harness check and require an exact Git task contract.
Generate L0/L1 context; L2/L3 are on-demand. Never discover the task from
recency. Route and context receipt stay bound to the candidate.

### Entry/outcome

Freeze owner decision, product outcome, named consumer, cheapest falsifier,
user-visible result, non-goals, evidence budget and replan trigger. Choose
`SPEC_ROUTE = NONE | PRD_LITE | DESIGN_SPEC | BOTH`; do not duplicate the task
contract.

Each substantial atom declares `DECISION_DELTA`, `UNCERTAINTY_REMOVED`,
`CAPABILITY_OR_EVIDENCE`, `STOP` and `NEXT`. Replan after a repeated blocker,
preparatory-only atom, impossible falsifier, second route/provider pivot or
evidence/time budget breach.

### Execute and review

Routine bounded delivery is autonomous. Use targeted tests; after bootstrap
the guarded merge is the sole project-bound gate executor for the unchanged
fingerprint. Code review is mandatory. Goal/DoD, architecture and refactor critics
are trigger-routed; unavailable subagents yield `SINGLE_AGENT_REVIEW_FALLBACK`
and the same deterministic validation.

### Finish and merge

Run Factory Fit, Product Horizon and capability radar. Record exact inventory,
head/tree, tests, limitations, non-claims and rollback. Capability candidates
grant no installation/credential/network/spend authority. Require exact-head CI
and then the exact owner PR/head phrase. Re-read machine state, evaluate v2,
merge once only on `AUTONOMOUS`, then verify the base-bound profile default
branch and its post-merge CI.
The guarded submission's `merge_commit` becomes the expected default-branch
head. The self-hashed submission is a mandatory input to
`--post-merge-readback --submission-receipt <GUARDED_SUBMISSION_JSON>`; the
separate hash-bound terminal receipt must prove the
ordered parents are exactly the frozen base then approved head, plus exact push
CI success. Read-only polling needs no
second owner approval; merge submission alone is never a completed delivery.

Validation commands are project-profile bindings, not portable-core guesses.
The guard executes them with `shell=false`; it never trusts a pre-existing local
receipt. A portable seed with null bindings may CHECK and build CONTEXT, but it
must report `delivery_gate_ready=false` and cannot merge until bootstrap binds
the repository's actual commands and exact PR-CI identity. In the normal path,
the guard runs the local focused primary once and consumes existing exact PR
CI as its full-suite evidence. The tracked-only fallback is exceptional and is
executed by that same guard only when the primary route is ineligible; it is
never a second pre-PR plus merge-time local run. The first harness installation
is delivered by the predecessor owner-approved route after one pre-PR
tracked-only gate; the new guard activates only after its policy/profile exist
on the default branch.

## Context and cloud export

Git is working project memory. `OWNER_MANAGED_OPTIONAL_EXPORT` means the harness
never prompts for Project Sources/Project Instruction replacement or smoke and
never uses cloud activation as an execution or DONE gate. Historical release
bytes remain audit-only.

## External boundary

This protocol grants no provider/API/RPC/WSS, credential, dependency adoption,
payment, deployment, settings, wallet, signer, transaction, cash, destructive
or force/history authority.
