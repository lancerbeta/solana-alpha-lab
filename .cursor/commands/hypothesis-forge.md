# Hypothesis Forge

Explicit owner invoke only. Runs `MANUAL_FALLBACK_UNTIL_GENERATOR` synthesis
through executable `preflight` → `forge-run` → FORGE_DRAFT (PROMPT A only when
next is `START_BASE`) → optional Prompt C after
`NO_WORTHY_HYPOTHESIS` (`HFIC-NEXT-V1.0`) → `freeze` → isolated Critic
→ optional `revise` / `classify` → `finalize`. Happy path: no owner copy/paste after `/hypothesis-forge`.

One `/hypothesis-forge` is `ONE_SLASH_ONE_BOUNDED_RUN` authority that expires at the
run owner-final or STOP. An HFIC session terminal is not automatically the
owner-final of the whole search. Token: `ZERO_MID_CYCLE_OWNER_INTERVENTION`.
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

Return `forge-run` `owner_readout`. Session `SYNTHESIS_COMPLETE` is **not**
automatically the bounded-run owner-final. Primary `KILL_*` is
**not** evening-complete while `session_state=RUNNER_UP_AWAITING_CRITIC`. After
session `NO_WORTHY`, Prompt C NEXT may be `WAIT_FOR_NEW_EVIDENCE`,
`FORWARD_DATA_OPTION_READY` or `CAPABILITY_OPTION_READY` (or deterministic wait
fallback). That session NEXT is **not** the bounded-run owner-final while
`forge-run` next is `START_V1`. Forge is incomplete until the **bounded run** owner-final, not merely a
session freeze. Session `NO_WORTHY` skips Critic and completes the HFIC
session at freeze, but `forge-run` `START_V1` means the evening run continues.
`PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED` / `PRIOR_MEMORY_RECORD_UNIDENTIFIED`
(BLOCKED; session not written; do not
launch Critic; `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`).
**Auto-launch** Independent Critic in new isolated context; no owner copy/paste.

No Git mutation, no provider calls, no experiment execution, no autonomous generator.

After `preflight`, show the `FORGE INPUT` owner block from `owner_forge_input`
(visible cohorts, active evidence set, historical calibration including
`caveat_router` when integrity is PASS, visibility, representations,
`forge_input_next`, `evidence_surface_mode`) before Prompt A. Then resolve
`forge-run` and print `owner_readout` (`FORGE RUN`) as the owner result — not
the raw JSON dump. `--persist` is `RESEARCH_ARTIFACT` `FORGE_RUN_RECEIPT`.
Branch on `forge-run` `next_action` before Prompt A. Session
`RETURN_EXISTING_SESSION` does not stop the run when next is `START_V1`.
Prompt A only when `forge-run` next is `START_BASE`, preflight `action` is not
`STOP`, and `forge_runnable` is true. Ordinary preflight machine-stops
`OBSERVABILITY_BLOCKED` / vision failure. If `forge_runnable` is still false,
stop; do not synthesize even if ordinary `action` is `START_NEW_SESSION`. Typed
`forge_input_next`: `WAIT_FOR_IMPORT_OR_STOP` / `STOP_OBSERVABILITY` / ready
`STOP_BEFORE_SYNTHESIS` (FORGE INPUT visibility, not slash authority, not
CONTROL next, not an observability halt). Always show `evidence_surface_mode`
(`ordinary` when JSON is null).
No-write diagnostic (same `--owner-focus` as preflight):

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-input --no-write --format json --owner-focus AUTO
```

Then resolve the bounded run. Print `owner_readout` first (`status:` DONE / NEXT / BLOCKED / READBACK).
`START_V1` auto-advances; do **not** run ordinary Prompt A for that next.
Owner pastes nothing. Same slash continues the V1 envelope via
`consume_start_v1_envelope` on CONTROL `FORGE_CONTEXT_PACKET` (no fake critic).
Freeze V1 with `ladder_freeze_preflight` from the `forge-run` JSON, not CONTROL
preflight. After a draft, `forge-run --persist --saved-draft-sha256`. Freeze/Critic
only after a V1 candidate exists (fixture stubs allowed), then
re-run `forge-run` to read real V1 artifacts. That wiring does not execute the
scientific V1 probe. Do not launch Critic on empty BASE. `RESUME_V1` uses `--saved-draft-sha256`, not the START helper.
Prompt C `WAIT` is not the owner-final while V1 is eligible.
`RETURN_EXISTING_RUN` is readback. Session `RETURN_EXISTING_SESSION` does not
mask `START_V1`. Resume a saved draft with `--saved-draft-sha256`. Persist on
an already-authorized slash:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --persist --format json --owner-focus AUTO
```

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write --format json --owner-focus AUTO
```

## Representation mode boundary

The normal slash command remains `ORDINARY`; its behavior and search budget are
unchanged. Ordinary BASE `NO_WORTHY` without CONTROL surface is
`CONTROL_REQUIRED` (`status: DONE`): evening complete, not a NEXT onto the
CONTROL slash. `--control-current-representation` remains the trajectory-blind
`CONTROL` mode and is expert-only. `NORMALIZED_TRAJECTORY_V1` is a `REPRESENTATION_CHALLENGER`
capability whose adapter is runtime-ready and not executed: it clones the
exact CONTROL context (Forge context for completed `NO_WORTHY`, critic packet
when a candidate was selected) and carries one anonymous histogram beside it.
It does not rebuild a newer context, inspect current cohort values, or invoke
a second ordinary Forge search.

For read-only routing/status from a supplied synthetic or runtime snapshot use:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge_representation.py representation-status --input <json>
```

`NORMALIZED_TRAJECTORY_V1_ELIGIBLE` is permission for a separately governed
one-run comparison, not execution. `RUNTIME_READY_NOT_EXECUTED` means the
seam can build a hash-bound envelope and the probe has not run; it is not
alpha, scientific PASS, or deployment evidence.
