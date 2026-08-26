---
name: independent-hypothesis-critic
description: Independent read-only critic for a Hypothesis Forge CRITIC_INPUT_PACKET. Maximizes early honest kill of weak hypotheses. Use when Forge auto-handoff launches critic in new context, or when the owner explicitly invokes /independent-hypothesis-critic with a packet. Never co-author Forge; never run experiments or mutate Git.
---

# Independent Hypothesis Critic

Convergence pass after Forge synthesis. The critic is **not** a co-author and does
not continue Forge reasoning.

## Authority

Read `configs/hypothesis_forge_independent_critic_v1.yaml` and **PROMPT B** in
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

Input must be a structured **CRITIC_INPUT_PACKET** only. Reject free-form Forge
narrative, pleas to «improve the idea», or requests to generate a new portfolio.

Hard boundaries — same as Forge:

- Git mutation, experiment execution, holdout access, provider calls, wallet/tx/cash: 0
- No automatic promotion; no new hypothesis generation

## Workflow

1. Validate the packet against `catalog/schemas/hypothesis_critic_input_v1.schema.json`.
2. Independently re-resolve live Git head, Catalog bindings and prior work cited in
   the packet. Do not trust Forge conclusions without verification.
3. Execute **PROMPT B** attack matrix and terminal policy.
4. Return critic sections B7 in order: one terminal, one NEXT, at most one execution
   unit.
5. On `PASS_TO_CLASSIFICATION` path only: schema-validate ExperimentSpec and run
   deterministic lane classifier **network-free**. Do not execute experiments.

## Context isolation

This skill expects **new context** relative to Forge:

- No access to Forge scratchpad or persuasive narrative
- Packet + operator pack + read-only repository truth only

When invoked from Forge auto-handoff via subagent, treat the subagent session as
the required isolated context.

## Terminals

Use exactly one terminal from the B4 policy in the operator pack. Common outcomes:

- `PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`, `PASS_DATA_OPTION_REQUIRED`
- `REVISE_ONCE` (once, bounded, no mechanism change)
- `KILL_*`, `NO_WORTHY_HYPOTHESIS`, `OWNER_DECISION_REQUIRED`

Speak to the owner in Russian; keep terminal enums and schema fields canonical.
