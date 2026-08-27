# Hypothesis Forge

Explicit owner invoke only. Runs `MANUAL_FALLBACK_UNTIL_GENERATOR` synthesis
through executable `preflight` → FORGE_DRAFT (PROMPT A) → `freeze` → isolated Critic
→ optional `revise` / `classify` → `finalize`. Happy path: no owner copy/paste after `/hypothesis-forge`.

Read and follow `.agents/skills/hypothesis-forge/SKILL.md` and
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

Optional owner focus (default `AUTO`):

```
OWNER_FOCUS=AUTO
```

Return one terminal + one NEXT after `SYNTHESIS_COMPLETE`. Forge is incomplete
until critic returns one terminal and one NEXT and finalize persists the cycle.
**Auto-launch** Independent Critic in new isolated context; no owner copy/paste.

No Git mutation, no provider calls, no experiment execution, no autonomous generator.
