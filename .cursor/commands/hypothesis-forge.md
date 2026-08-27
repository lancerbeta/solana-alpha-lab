# Hypothesis Forge

Explicit owner invoke only. Runs `MANUAL_FALLBACK_UNTIL_GENERATOR` synthesis
through executable `preflight` → FORGE_DRAFT (PROMPT A) → optional Prompt C after
`NO_WORTHY_HYPOTHESIS` (`HFIC-NEXT-V1.0`) → `freeze` → isolated Critic
→ optional `revise` / `classify` → `finalize`. Happy path: no owner copy/paste after `/hypothesis-forge`.

One `/hypothesis-forge` is `ONE_SLASH_ONE_SESSION` authority that expires at the
final terminal or STOP. Token: `ZERO_MID_CYCLE_OWNER_INTERVENTION`.
`PASS_TO_CLASSIFICATION` and exactly one bounded `REVISE_ONCE` continue
automatically under the same slash. After `NO_WORTHY_HYPOTHESIS`, the same slash
runs Prompt C (`HFIC-NEXT-V1.0`) and freeze `--next-action` with
`ZERO_MID_CYCLE_OWNER_INTERVENTION`. Do not ask the owner to press Run or approve
an RDP write between preflight, freeze, Critic, revision/classification and
finalize. If isolated Critic context cannot launch, return typed
`AUTO_HANDOFF_UNAVAILABLE`; do not silently self-criticize.

If the host platform requires command approval, request at most one narrowly
scoped batch at cycle start for
`uv run --locked --managed-python python -B scripts/hypothesis_forge.py ...`,
process-owned OS temp files, and append-only writes under the resolved canonical
RDP. Do not request broad shell/filesystem authority or a bare `python`
interpreter. Required runtime is CPython 3.13.14 via that prefix.

Read and follow `.agents/skills/hypothesis-forge/SKILL.md` and
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

Optional owner focus (default `AUTO`):

```
OWNER_FOCUS=AUTO
```

Return one terminal + one NEXT after `SYNTHESIS_COMPLETE`. After `NO_WORTHY`,
NEXT is `WAIT_FOR_NEW_EVIDENCE`, `FORWARD_DATA_OPTION_READY` or
`CAPABILITY_OPTION_READY` (or deterministic wait fallback). Forge is incomplete
until critic returns one terminal and one NEXT and finalize persists the cycle,
except `NO_WORTHY` which skips Critic and is complete at freeze.
**Auto-launch** Independent Critic in new isolated context; no owner copy/paste.

No Git mutation, no provider calls, no experiment execution, no autonomous generator.
