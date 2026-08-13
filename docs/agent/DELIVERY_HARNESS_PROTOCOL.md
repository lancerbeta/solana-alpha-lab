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

Routine bounded delivery is autonomous. Use targeted tests and one full-gate
owner. Code review is mandatory. Goal/DoD, architecture and refactor critics
are trigger-routed; unavailable subagents yield `SINGLE_AGENT_REVIEW_FALLBACK`
and the same deterministic validation.

### Finish and merge

Run Factory Fit, Product Horizon and capability radar. Record exact inventory,
head/tree, tests, limitations, non-claims and rollback. Capability candidates
grant no installation/credential/network/spend authority. Require exact-head CI
and then the exact owner PR/head phrase. Re-read machine state, evaluate v2,
merge once only on `AUTONOMOUS`, then verify exact main and post-merge CI.

## Context and cloud export

Git is working project memory. `OWNER_MANAGED_OPTIONAL_EXPORT` means the harness
never prompts for Project Sources/Project Instruction replacement or smoke and
never uses cloud activation as an execution or DONE gate. Historical release
bytes remain audit-only.

## External boundary

This protocol grants no provider/API/RPC/WSS, credential, dependency adoption,
payment, deployment, settings, wallet, signer, transaction, cash, destructive
or force/history authority.
