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
Do not accept the outer frozen envelope, Forge scratchpad, or hidden session
context alongside the packet. Return `hypothesis_critic_result_v1`. The critic
does not persist; `finalize` owns Research Data Plane writes.

## Copied identity — never generated

Every required identity field of `hypothesis_critic_result_v1` is
copied/bound identity, never generated identity, from the packet plus
read-only repo truth. Do **not** invent
`HFIC-UNBOUND-*`, reconstruct `session_id` from `candidate_id`, or copy identity
from a Forge envelope you were not given.

Copy/bind exactly:

- `session_id` ← `CRITIC_INPUT_PACKET.session_id` (`HFIC-SESS-...`)
- `selected_candidate_id` ← `selected_candidate.candidate_id`
- `critic_input_packet_sha256` ← canonical SHA256 of the exact packet bytes
- `selected_definition_sha256` ← canonical selected-candidate identity hash
  from packet fields via repo identity algorithm, as applicable

A `packet_version=1.1` or `1.2` packet without `session_id` is incomplete. Do **not**
emit `hypothesis_critic_result_v1` and do **not** infer the missing field.
Return `STATUS=INCOMPLETE_CRITIC_INPUT_PACKET` and
stop. Generator prompt versions `HFIC-V1.1` and `HFIC-V1.2` are both accepted;
critic result identity remains `HFIC-V1.1`.
`OWNER NEXT=RE_RUN_FREEZE_AND_PASTE_PACKET_WITH_SESSION_ID`.

If `finalize` later reports `CRITIC_SESSION_MISMATCH`, copy
`CRITIC_INPUT_PACKET.session_id` into the result and retry once. Do not invent
`HFIC-UNBOUND-*`. If the packet still has no `session_id`, use the incomplete
path above. Finalize keeps fail-closed equality
`critic_result.session_id == frozen.session_id`.

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
- No outer frozen envelope, Forge narrative, or hidden session_id channel

When invoked from Forge auto-handoff via subagent, treat the subagent session as
the required isolated context.

## Terminals

Use exactly one terminal from operator pack **B4** — the sole PASS entry before
classification is `PASS_TO_CLASSIFICATION`. Do not emit `PASS_FAST_LANE_READY`,
`PASS_CHANGE_LANE_REQUIRED` or `PASS_DATA_OPTION_REQUIRED` without completing
**B5**: schema-valid ExperimentSpec plus deterministic offline `classify_lane()`.

B4 terminals (choose one):

- `PASS_TO_CLASSIFICATION` — then run B5 classifier mapping
- `REVISE_ONCE` — bounded repair once; no mechanism change
- `KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED`, `KILL_MECHANISM`, `KILL_PIT_OR_LEAKAGE`,
  `KILL_EXECUTION_OR_ECONOMICS`, `KILL_DATA_INFEASIBLE`,
  `KILL_STATISTICALLY_UNIDENTIFIABLE`, `KILL_LOW_INFORMATION_VALUE`,
  `KILL_PREPARATORY_LOOP`, `KILL_UNBOUND_EVIDENCE`
- `NO_WORTHY_HYPOTHESIS`, `OWNER_DECISION_REQUIRED`

After B5 classifier only (never by narrative):

- `PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`, `PASS_DATA_OPTION_REQUIRED`

Record `lane_classifier_terminal` and `classifier_receipt_present: true` in the
synthesis handoff whenever the final terminal is post-classification.

Speak to the owner in Russian; keep terminal enums and schema fields canonical.
