---
adr_id: ADR-004
title: Owner attention gate and route-specific merge authority
status: OWNER_DESIGN_APPROVED_IMPLEMENTATION_CANDIDATE
as_of: 2026-08-08
owner_task: CTRL-OWNER-ATTENTION-GATE
supersedes:
  - ADR-003:merge-authority-only
contains_secrets: false
---

# ADR-004 — Owner attention gate and route-specific merge authority

## Context

Routine confirmation prompts became an attention tax: they asked the goal
owner to approve engineering evidence already owned by tests, validation and
CI. Repetition weakens review without transferring useful product knowledge.
At the same time, unconditional full access would blur material product,
external-system and safety boundaries.

## Decision

Adopt `control/owner_attention_gate_v1.yaml` as the active machine-readable
attention and route policy.

The goal owner owns mission, hypotheses, estimands, product meaning and
priority, budget and cash caps, risk appetite, material data-source choices,
external-material authority and physically user-only UI activation. Codex owns
routine engineering choices and evidence quality inside the accepted bounded
objective.

For `LOCAL_WORK_CODEX`, Codex may perform an ordinary PR merge without another
per-PR prompt only when the deterministic gate returns `AUTONOMOUS` for the
exact PR head and every declared merge precondition is true. It must preserve
the branch, avoid settings/protection bypass, read back the exact merged main
commit and require post-merge main CI.

For `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`, Cursor remains `EXECUTION_ONLY` and
never merges. That route has no Codex auto-merge grant; merge returns to the
Project Chat/owner attention boundary. `GPT_ONLY` also has no auto-merge grant.

A failed machine check returns `DENY`, not a softer human approval prompt.
Canonical acceptance and `DONE` remain GPT control-plane decisions after
evidence reconciliation.

## Alternatives

| Alternative | Decision |
|---|---|
| Keep exact confirmation for every PR | Rejected: repeated low-information owner work |
| Remove only the merge prompt | Rejected: leaves inconsistent approval rules elsewhere |
| Unconditional full-access autonomy | Rejected: unsafe across external, destructive and semantic boundaries |
| Route-specific deterministic gate | Accepted: removes routine noise while preserving material control |

## Consequences

- active policy surfaces and lifecycle skills share one positive decision
  recipe;
- CI rejects restoration of the old per-PR approval loop on active surfaces;
- local Codex merge is evidence-bound, not inferred from a PR or passing test;
- Cursor and baton trust boundaries remain unchanged except for explicit
  reference to this gate;
- Project Instruction v3.4 requires a later user UI replacement/read-back and
  is not activated by this ADR.

## Rollback and trigger review

Any unauthorized/material merge, Cursor merge, protection bypass, branch
deletion, or merge of a failed/stale exact head disables autonomous merge and
requires a repair ADR. Review the policy after ten local Codex deliveries for
owner interruptions, repair commits and false gate classifications. No event
alone rewrites historical evidence.
