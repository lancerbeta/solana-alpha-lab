---
name: hypothesis-forge
description: Manual Hypothesis Forge for Solana Alpha Lab under MANUAL_FALLBACK_UNTIL_GENERATOR. Use only when the owner explicitly invokes /hypothesis-forge. Returns FORGE_REPORT and CRITIC_INPUT_PACKET, then auto-launches Independent Critic in new isolated context. No Git mutation, provider calls, experiment execution or autonomous generator.
---

# Hypothesis Forge

Use **only** when the owner explicitly invokes `/hypothesis-forge`. Do not run Forge
from orientation, autonomous delivery, or implicit continuation phrases.

Manual hypothesis synthesis contour for Solana Alpha Lab while
`MANUAL_FALLBACK_UNTIL_GENERATOR` remains active. Design and discovery only.

## Authority

Read `configs/hypothesis_forge_independent_critic_v1.yaml` and the operator pack at
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

Hard boundaries — zero tolerance:

- Git mutation, branch, PR, task or evidence file creation
- Experiment execution or viewing new outcomes for ranking
- Untouched/forward holdout access
- Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash spend
- Autonomous Hypothesis Generator («magic ball»)

Allowed: read-only Git/Catalog navigation, bounded prior-work query, design packets.

## Workflow

`REALITY → OPPORTUNITY_MAP → CANDIDATE_PORTFOLIO → PARETO → FORGE_REPORT → CRITIC_INPUT_PACKET → AUTO CRITIC`

1. Restore live Git truth from repository front door (`AGENTS.md`, harness, Catalog).
   Do not trust stale chat exports as authority.
2. Execute **PROMPT A** from the operator pack (`HFIC-V1.0`).
3. Return the full **FORGE_REPORT** sections A13 in order, ending with a canonical
   **CRITIC_INPUT_PACKET** that validates against
   `catalog/schemas/hypothesis_critic_input_v1.schema.json`.
4. Set `generator_prompt_version: HFIC-V1.0` and keep all authority counters at `0`.

## Mandatory auto-handoff (non-negotiable)

Forge is **not complete** when the packet is printed. The owner must not need to
remember step 2.

Immediately after a valid `CRITIC_INPUT_PACKET`:

1. Emit a synthesis handoff receipt with `synthesis_status: PENDING_CRITIC` per
   `catalog/schemas/hypothesis_forge_synthesis_handoff_v1.schema.json`.
2. **Launch Independent Critic in a new isolated context** using one of:
   - `Task` subagent with read-only critic instructions and **only** the packet
     (no Forge narrative, no intermediate reasoning); or
   - instruct the owner to open a **new chat** and run `/independent-hypothesis-critic`
     with the packet — only if subagent launch is unavailable.
3. Do not mark the evening cycle done, do not propose execution tasks, and do not
   treat synthesis as finished until the critic returns one terminal and one NEXT.
4. After critic returns, emit handoff with `synthesis_status: SYNTHESIS_COMPLETE`,
   `critic_terminal`, and `critic_report_present: true`.

If packet validation fails, return `STATUS=NOT_READY`, keep
`synthesis_status: FORGE_NOT_READY`, and one repair action. Do not launch critic
on an invalid packet.

## Output contract

Speak to the owner in Russian. Keep schemas, enums, packet fields and paths
canonical in English.

Never end with a conditional backlog. One execution unit maximum per cycle.

## Model effort

Use `SOL_XHIGH` for mechanism/PIT/estimand reasoning. Critic handoff may use the
same or a different strong model; isolation matters more than model identity.
