# Hypothesis Forge

Explicit owner invoke only. Runs `MANUAL_FALLBACK_UNTIL_GENERATOR` synthesis
through executable `preflight` → FORGE_DRAFT (PROMPT A) → optional Prompt C after
`NO_WORTHY_HYPOTHESIS` (`HFIC-NEXT-V1.0`) → `freeze` → isolated Critic
→ optional `revise` / `classify` → `finalize`. Happy path: no owner copy/paste after `/hypothesis-forge`.

One `/hypothesis-forge` is `ONE_SLASH_ONE_SESSION` authority that expires at the
final terminal or STOP. Token: `ZERO_MID_CYCLE_OWNER_INTERVENTION`.
`PASS_TO_CLASSIFICATION` and exactly one bounded **primary** `REVISE_ONCE`
continue automatically under the same slash. A final primary `KILL_*` continues
once for the already-frozen runner-up (`RUNNER_UP_AWAITING_CRITIC` → isolated
Critic #2 on the pre-frozen C2 packet only). C2 `REVISE_ONCE` does **not**
auto-continue: persist `PAUSE` / `RUNNER_UP_REVISION_REQUIRED`, no C2 wording
repair, no C3, no new AUTO search. After `NO_WORTHY_HYPOTHESIS`, the same slash
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

Return one terminal + one NEXT after `SYNTHESIS_COMPLETE`. Primary `KILL_*` is
**not** evening-complete while `session_state=RUNNER_UP_AWAITING_CRITIC`. After
`NO_WORTHY`, NEXT is `WAIT_FOR_NEW_EVIDENCE`, `FORWARD_DATA_OPTION_READY` or
`CAPABILITY_OPTION_READY` (or deterministic wait fallback). Forge is incomplete until `finalize` persists `SYNTHESIS_COMPLETE`, except `NO_WORTHY` (skips Critic; complete at freeze) and
`PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED` / `PRIOR_MEMORY_RECORD_UNIDENTIFIED`
(BLOCKED; session not written; do not
launch Critic; `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`).
**Auto-launch** Independent Critic in new isolated context; no owner copy/paste.

No Git mutation, no provider calls, no experiment execution, no autonomous generator.

## Representation mode boundary

The normal slash command remains `ORDINARY`; its behavior and search budget are
unchanged. `--control-current-representation` remains the trajectory-blind
`CONTROL` mode. `NORMALIZED_TRAJECTORY_V1` is only a dormant
`REPRESENTATION_CHALLENGER` capability: a later bounded adapter clones the
exact CONTROL packet and carries one anonymous histogram beside it. It does
not rebuild a newer context, inspect current cohort values, or invoke a second
ordinary Forge search.

For read-only routing/status from a supplied synthetic or runtime snapshot use:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge_representation.py representation-status --input <json>
```

`NORMALIZED_TRAJECTORY_V1_ELIGIBLE` is permission for a separately governed
one-run comparison, not execution. `IMPLEMENTED_DORMANT_NOT_EXECUTED` means
the code exists and the probe has not run; it is not alpha, scientific PASS,
or deployment evidence.
