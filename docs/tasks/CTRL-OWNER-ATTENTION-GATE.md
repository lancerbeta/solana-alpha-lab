# CTRL-OWNER-ATTENTION-GATE — Route-specific owner attention and merge authority

## Objective

Replace repeated routine approval prompts with one deterministic
`OWNER_ATTENTION_GATE_V1`. The goal owner keeps product meaning, budget, risk,
external-material and user-only decisions. The elected engineering route owns
bounded implementation quality through tests, validation and read-back.

## Owner decision

`OWNER_ATTENTION_POLICY_DESIGN_APPROVED` on 2026-08-08.

## Scope

- active repository authority, execution-router, baton and Cursor policy;
- a deterministic gate evaluator and adversarial tests;
- `start-solana-task` and `finish-solana-task` lifecycle alignment;
- a full Project Instruction v3.4 UI candidate;
- Catalog and generated navigation propagation.

Historical task records, receipts and negative evidence remain append-only.
Project Sources are unchanged unless Finish Gate finds an actual semantic-role
delta.

## Decision contract

- `AUTONOMOUS`: bounded routine work, or an exact-head ordinary PR merge by
  Codex on `LOCAL_WORK_CODEX` after every machine precondition passes.
- `OWNER_ATTENTION_REQUIRED`: material owner decision, user-only activation,
  external-material boundary, authorization recovery, unresolved safety/truth
  conflict, stricter stop, or merge on a non-local route.
- `DENY`: unbound scope, forbidden actor/route, unknown action, Cursor merge,
  or failed merge precondition. Owner confirmation is not a bypass for failed
  machine evidence.

## Non-claims

- Cursor never merges.
- Auto-merge does not grant canonical acceptance or `DONE`.
- The policy grants no provider, credential, wallet, transaction, cash,
  deployment, settings, destructive or user-UI authority.
- A repository candidate does not activate Project Sources or Project
  Instruction.

## Validation and delivery

Targeted tests must cover every decision class, every owner trigger, route
separation, failed exact-head/CI evidence and stale approval-loop wording.
Delivery requires the tracked-only full gate, exact PR-head CI, ordinary merge,
exact main read-back and post-merge main CI. Branch deletion remains forbidden.
