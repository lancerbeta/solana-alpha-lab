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
- the portable seed is a hash-inventoried, standard-library-only bundle bound
  to one live Git origin; no hidden Solana virtualenv or placeholder repository
  is needed;
- guarded merge uses an atomic expected-head comparison and is incomplete until
  the self-hashed guarded submission is a mandatory input to a separate
  hash-bound receipt proving exact default-branch ancestry and successful push
  CI;
- first installation is a one-time predecessor-route migration because the
  frozen base cannot trust policy/profile bytes that do not yet exist there;
  the new guard deliberately denies self-merge and activates only from the
  first default-branch commit that contains the reviewed owners;
- technical delivery remains distinct from semantic acceptance and DONE.

## Official platform fit

The context split follows current OpenAI product mechanics rather than a local
prompt convention. Codex discovers layered `AGENTS.md` files once per run and
has a default combined project-instruction ceiling of 32 KiB, so the repository
root stays deliberately lean and stable:
<https://learn.chatgpt.com/docs/agent-configuration/agents-md>.

Repeatable workflow detail lives in the repository skill because Codex skills
use progressive disclosure: only name/description occupy the initial context,
then full `SKILL.md` is loaded on demand. Repository skills under
`.agents/skills` are a supported discovery scope:
<https://learn.chatgpt.com/docs/build-skills>.

Task and evidence bytes therefore remain Git-addressed and selected by the
context receipt rather than copied into always-on instructions. No plugin, MCP
or separate memory service is justified until the capability radar observes a
named external consumer or repeated measured retrieval failure.

## Rollback

Revert ADR-005 and the active adapters as one candidate only after proving a
material direct-route defect. Historical baton remains available for analysis,
but reactivation requires a new owner-approved successor ADR and exact task; a
file, Issue or old receipt is insufficient.
