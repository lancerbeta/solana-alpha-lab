# Independent Hypothesis Critic

Recovery or explicit critic invoke. Use when Forge already produced a
`CRITIC_INPUT_PACKET`, or when auto-handoff needs a manual retry in a **new chat**.

Read and follow `.agents/skills/independent-hypothesis-critic/SKILL.md`.

Paste **only** the YAML packet below this line — not Forge narrative:

```
CRITIC_INPUT_PACKET:
<paste packet here>
```

Return one terminal and one NEXT. No experiment execution, no Git mutation, no
provider calls, no new hypothesis portfolio.
