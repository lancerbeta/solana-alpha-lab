# Independent Hypothesis Critic

Recovery or explicit critic invoke. Use when Forge already produced a
`CRITIC_INPUT_PACKET`, or when auto-handoff needs a manual retry in a **new chat**.

Read and follow `.agents/skills/independent-hypothesis-critic/SKILL.md`.

Paste **only** the YAML packet below this line — not Forge narrative, not the
outer frozen envelope:

```
CRITIC_INPUT_PACKET:
<paste packet here>
```

Copy `session_id`, `selected_candidate.candidate_id`, packet SHA256, and
selected-definition identity from the packet. Never generate
`HFIC-UNBOUND-*` or reconstruct `session_id`.

If the pasted packet is `packet_version=1.1` and has no `session_id`: do not
return a critic result. Output `STATUS=INCOMPLETE_CRITIC_INPUT_PACKET` and
`OWNER NEXT=RE_RUN_FREEZE_AND_PASTE_PACKET_WITH_SESSION_ID`.

If `finalize` reports `CRITIC_SESSION_MISMATCH`: copy packet `session_id` into
the result and retry once. Do not invent a session id.

Return one terminal and one NEXT. No experiment execution, no Git mutation, no
provider calls, no new hypothesis portfolio.
