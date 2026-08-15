---
name: autonomous-delivery
description: Receding-horizon delivery controller over Delivery Harness. Restores Git truth, challenges the current plan, selects one bounded atom, executes it to PR, and stops only at a real owner gate. Use when the owner asks to continue autonomous project delivery or choose the next best project step after restoring evidence and reconsidering the current plan (го дальше, что дальше, продолжай, следующий шаг, поднимем голову, continue, what next).
---

# Autonomous Delivery

Overlay on Delivery Harness, not a second control plane. Procedures live in
`.agents/skills/delivery-harness/SKILL.md`. This skill chooses **which** atom
and **when** to stop; the harness owns **how** to deliver and merge.

Inside this repository, continue/what-next owner intents belong here. User-level
`start-solana-task` / `finish-solana-task` must not select work, resurrect
`GITHUB_BATON`, require cloud smoke, or treat those phrases as automatic `DONE`.

## 1. Activation

Relevant when the owner wants the next best project step, including:

`го дальше` / `что дальше` / `продолжай` / `следующий шаг` / `поднимем голову`
/ `continue` / `what next`

`/autonomous-delivery` is the explicit invoke. Manual invoke does not skip
truth restore or owner gates.

Never take the next `TASK-XX` by number, recency, branch name, or roadmap
position alone.

## 2. Restore truth

Before mutation, fill this internally from Git L0/L1 plus due time gates.
Missing fact = explicit gap, not a guess.

```yaml
orientation:
  north_star:
  last_validated_outcome:
  last_outcome_nonclaims:
  current_reality:
  active_or_open_work:
  blockers_and_time_gates:
  downstream_decision:
  product_or_evidence_gap:
  capability_gap:
  strongest_new_evidence_since_plan:
```

Ask: what most limits progress from proved reality to the next meaningful
product outcome?

Do not confuse: recent task with best next; CI with product outcome;
implemented capability with demonstrated need; activity with uncertainty
reduction; roadmap position with evidence-based priority.

## 3. Challenge the plan

Roadmap is the current canonical sequence, not a nailed-down future. On an
atom boundary, new-atom select, `поднимем голову`, repeated blocker, or
evidence that destroys the next premise, load
[references/roadmap-challenge.md](references/roadmap-challenge.md) and return
exactly one: `KEEP | PATCH | REORDER | REBASE`.

Default cheap: `KEEP` or `PATCH`. Do not run a strategy audit on every commit.
A material verdict must update authoritative artifacts before further work;
silent divergence is forbidden.

## 4. Routing verdict

Pick exactly one, then act if authority already exists:

| Verdict | When |
| --- | --- |
| `CONTINUE` | Unfinished exact atom; premise valid; next step still in scope |
| `REPLAN` | Contract/sequence must change before more work |
| `SELECT` | Atom done or absent; a new bounded atom can be chosen |
| `STRATEGY` | Product/estimand/architecture question blocks implementation |
| `BOTTLENECK` | Outcome blocked by a named missing capability/control/data property |
| `RESEARCH` | Named decision gap cheaper to close with targeted research than code |
| `OWNER_DECISION` | Real material, user-only, external, money, destructive, or merge gate |

`STRATEGY` and `REBASE` are exceptional. Do not spend the turn on strategy
theater when one bounded atom is already justified.

## 5. One atom

No owner menu of equivalent technical options. Choose the strongest bounded
atom by this heuristic (not a formula):

```text
named downstream decision/consumer
× information gain / uncertainty reduction
× product leverage
× reversibility / option value
÷ complexity
÷ rework risk
÷ operational burden
```

Prefer: current bottleneck, cheap falsifier, observable outcome, independent
verification, no speculative infrastructure, no irreversible complexity,
helps the product not only the last task.

If the fork is material, keep only `strongest_rejected_alternative` and
`why_rejected_now` in the contract.

## 6. Product+System contract

Before a new implementation atom, load
[references/product-system-contract.md](references/product-system-contract.md)
and emit/update the **existing** exact task contract. Do not add a parallel
PRD/SSD/plan file for the same atom.

`CONTINUE` uses the current contract unless scope drifted.

## 7. Execute

Harness loop; no ceremonial owner stops between design/code/tests/review:

`CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH -> EXACT MERGE GATE -> READ-BACK`

Routine in-scope work is autonomous: local writes, tests, generated
propagation, Catalog/registry transaction, ordinary commits, non-force push,
PR, review, CI, repair. After a meaningful milestone, re-check ground truth
before stacking more steps.

## 8. Failure then replan

First failure is not `OWNER_DECISION`. Observe → classify → cheapest
defensible repair → rerun → verify.

`REPLAN` when: the same material blocker survives a reasonable repair; a
second provider/route pivot appears; the design premise is false; the write
set materially spreads; budget is breached; repair needs a different
architecture boundary. Do not buy a bad route with more tokens.

## 9. Research gate

No deep/broad research without:

```yaml
research_gate:
  decision_gap:
  decision_it_changes:
  minimum_evidence_needed:
  stop_condition:
```

Hit `stop_condition`, return to delivery. Research without a named decision
is scope drift. After the first material blocker, reuse-first
(`ADOPT -> WRAP -> FORK -> BUILD`) still grants no provider/dependency/cost
authority.

## 10. Review

Passing tests are required and do not prove product outcome. Risk-route as
the harness: code review always; goal/DoD for new/changed outcomes;
architecture for contracts/schemas/boundaries/security/multi-component;
refactor only after correctness plus a measured signal. Unavailable
subagents → `SINGLE_AGENT_REVIEW_FALLBACK` plus the same deterministic
checks.

Critics hunt: false DONE, wrong outcome, hidden regression, invalid
assumption, architecture drift, weak oracle, scope creep, new
operational/security burden. No multi-agent ceremony for routine change.

## 11. Context budget

`control plane → exact task → direct dependencies → evidence needed now`.
Do not load the repository wholesale. If the run loses coherence, stop at a
clean verifiable point and persist a compact Git-native checkpoint:

```yaml
checkpoint:
  outcome_target:
  current_state:
  completed:
  evidence:
  decisions:
  current_head:
  unresolved:
  next_exact_action:
```

State, not chain-of-thought. L2/L3 only for a named gap or evidence dispute.

## 12. Durable learning

Persist only what must outlive this chat: validated decision, new invariant,
architecture delta, negative evidence, reusable procedure, recurring failure
mode, capability boundary. Git is not a transcript archive.

A repeated error may evolve `written guidance → deterministic check →
reusable script/skill/control` only after proved recurrence.

## 13. Owner attention

Owner attention is expensive. Do not stop for a new file, implementation
choice, finished design phase, failing test, ordinary commit, PR open/update,
or a routine critic defect.

Stop only on harness v2 gates: material product/estimand/data-contract/safety
change; paid obligation; credential/access; wallet/signer/transaction;
destructive/history/settings; material external/deploy; unresolved
truth/safety conflict; exact merge. This skill does not widen harness-gated
authority.

## 14. Exact merge and report

Carry the atom to a complete exact PR. Before asking for merge:

```yaml
merge_readiness:
  scope_matches_contract:
  product_outcome_verified:
  tests:
  deterministic_checks:
  required_review:
  ci:
  exact_base:
  exact_head:
  unresolved_material_findings:
  state_catalog_registries_reconciled:
```

Green PR is not `DONE`. Then stop. After the exact owner phrase, run only the
repository guarded merge and post-merge read-back.

```text
MERGE_READY=<YES|NO>

OUTCOME:
EVIDENCE:
PR:
HEAD:
ROADMAP: <KEEP|PATCH|REORDER|REBASE + delta>
KNOWN_LIMITATIONS:
NEXT_AFTER_MERGE:
OWNER_ACTION:
```
