# Hypothesis Forge

Explicit owner invoke only. Runs `MANUAL_FALLBACK_UNTIL_GENERATOR` synthesis.

Read and follow `.agents/skills/hypothesis-forge/SKILL.md` and
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

Optional owner focus (default `AUTO`):

```
OWNER_FOCUS=AUTO
```

Return full FORGE_REPORT + canonical CRITIC_INPUT_PACKET, then **auto-launch**
Independent Critic in new isolated context per the skill. Forge is incomplete
until critic returns one terminal and one NEXT.

No Git mutation, no provider calls, no experiment execution, no autonomous generator.
