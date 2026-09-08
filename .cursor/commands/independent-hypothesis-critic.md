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

If the pasted packet is `packet_version=1.1`, `1.2`, or `1.3` and has no
`session_id`: do not return a critic result. Output
`STATUS=INCOMPLETE_CRITIC_INPUT_PACKET` and
`OWNER NEXT=RE_RUN_FREEZE_AND_PASTE_PACKET_WITH_SESSION_ID`.

If the pasted packet is `packet_version=1.3` and has no `prior_memory`: do not
return a critic result and do not walk ResearchStore. Output
`STATUS=INCOMPLETE_CRITIC_INPUT_PACKET` and
`OWNER NEXT=RE_RUN_FREEZE_AND_PASTE_PACKET_WITH_PRIOR_MEMORY`.
Historical `1.0` / `1.1` / `1.2` packets remain readable without `prior_memory`.
Do not reconstruct or fabricate `prior_memory` for historical `1.2`.

For `packet_version=1.3`, packet `prior_memory` is the sole research-memory
input. Do not open ResearchStore or active RDP for prior recall.

If `finalize` reports `CRITIC_SESSION_MISMATCH`: copy packet `session_id` into
the result and retry once. Do not invent a session id.

Return one terminal and one NEXT. No experiment execution, no Git mutation, no
provider calls, no new hypothesis portfolio.
