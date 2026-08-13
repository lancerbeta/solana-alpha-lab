---
adr_id: ADR-005
title: Git-native direct Delivery Harness
status: ACCEPTED_IMPLEMENTED_CANDIDATE
as_of: '2026-08-14'
owner_task: CTRL-DELIVERY-HARNESS-V1
supersedes:
  - ADR-003:active-routing
  - ADR-004:direct-route-merge-authority
contains_secrets: false
---

# ADR-005 — Git-native direct Delivery Harness

## Context

The former GPT-to-GitHub-baton-to-Cursor chain duplicated policy, consumed
always-on context and denied Cursor the routine delivery/guarded merge rights
already available to Codex. Cloud Project Sources also became an unnecessary
runtime ceremony once permanent project artifacts were available in Git.

## Decision

Adopt `DELIVERY_HARNESS_V1` with three active routes:

- `DIRECT_CODEX_DELIVERY`;
- `DIRECT_CURSOR_DELIVERY`;
- `DESIGN_ONLY`.

Cursor and Codex consume the same Git core, exact task context projection,
owner-attention v2 policy and delivery gates. Both autonomously perform bounded
routine delivery. Both require one exact owner PR/head approval and an unchanged
machine gate before an ordinary merge.

Git is working project memory. Cloud bundle/Project Instruction is
`OWNER_MANAGED_OPTIONAL_EXPORT`: no execution/DONE gate, reminder, replacement
request or smoke. Historical releases remain audit evidence.

The old baton becomes `LEGACY_GITHUB_BATON_DORMANT`. Active Cursor adapters are
removed; historical scripts, contracts, fixtures, tests, receipts and protocol
remain discoverable and cannot reactivate themselves.

## Consequences

- one lean root front door and scoped Cursor rules reduce context duplication;
- one repository skill owns delivery workflow; Cursor commands are thin;
- optional read-only critics isolate review context without becoming a
  correctness dependency;
- capability radar may recommend one plugin/tool only after a measured trigger
  and never grants installation or credentials;
- technical delivery remains distinct from semantic acceptance and DONE.

## Rollback

Revert ADR-005 and the active adapters as one candidate only after proving a
material direct-route defect. Historical baton remains available for analysis,
but reactivation requires a new owner-approved successor ADR and exact task; a
file, Issue or old receipt is insufficient.
