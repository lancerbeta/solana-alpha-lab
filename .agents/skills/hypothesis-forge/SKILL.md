---
name: hypothesis-forge
description: Manual Hypothesis Forge for Solana Alpha Lab under MANUAL_FALLBACK_UNTIL_GENERATOR. Use only when the owner explicitly invokes /hypothesis-forge. Runs executable preflight → freeze → isolated Critic → optional revise/classify → finalize. No Git mutation, provider calls, experiment execution or autonomous generator.
---

# Hypothesis Forge

Use **only** when the owner explicitly invokes `/hypothesis-forge`. Do not run Forge
from orientation, autonomous delivery, or implicit continuation phrases.

Manual hypothesis synthesis contour for Solana Alpha Lab while
`MANUAL_FALLBACK_UNTIL_GENERATOR` remains active. Prompt version `HFIC-V1.2`
(new sessions). Historical `HFIC-V1.1` drafts/receipts remain readable.
V1.2 adds deterministic feature grounding, typed unresolved requirements,
diagnostics-only `structural_signature_v1_sha256` (not HFIC-CAND identity),
and read-only `diagnostics --last N` (1..20).

Canonical entrypoint: `scripts/hypothesis_forge.py`.
Operator-executable prefix:
`uv run --locked --managed-python python -B scripts/hypothesis_forge.py`.
Required interpreter: CPython `3.13.14`. Do not invoke a bare workstation `python`.

## Authority

Read `configs/hypothesis_forge_independent_critic_v1.yaml` and the operator pack at
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

One explicit `/hypothesis-forge` is scoped authorization for exactly one HFIC
session (`ONE_SLASH_ONE_SESSION`), expiring at final terminal/STOP.
`ZERO_MID_CYCLE_OWNER_INTERVENTION`: do not ask the owner to press Run or
approve an RDP write between preflight, freeze, Critic, revision/classification
and finalize. `PASS_TO_CLASSIFICATION` and exactly one bounded **primary** `REVISE_ONCE`
remain inside the original slash authority and continue automatically.
A final primary `KILL_*` continues once as isolated Critic #2 on the pre-frozen
C2 packet. C2 `REVISE_ONCE` does not auto-continue (`RUNNER_UP_REVISION_REQUIRED`).
After Prompt A `NO_WORTHY_HYPOTHESIS`, the same slash automatically runs
Prompt C (`HFIC-NEXT-V1.0`) and freeze `--next-action` without owner intervention.

Authorized without additional owner questions: read-only Git/Catalog navigation;
in general Forge, read-only active RDP navigation; preflight and safe offline
commissioning on the same canonical data root if genuinely required;
process-owned OS temp files; append-only RDP writes for context artifact,
session/cycle, all candidate versions, frozen Critic packet, Critic result,
revision receipt, classifier receipt, decisions, session receipt, next
epistemic action and terminal; automatic isolated Critic handoff; network-free
deterministic lane classification; finalize; replay/resume/`prove-runtime`;
cleanup of process-owned temp files.

In `CURRENT_REPRESENTATION_CONTROL_V1`, Prompt A RDP access is limited to the
coarse `FORGE_CONTEXT_PACKET` and labels/fingerprints already in that packet —
not raw current lifecycle observation rows, parquet bodies, or trajectories.

Before proposing `PASS_CHANGE_LANE_REQUIRED`, `CAPABILITY_OPTION_READY`, a new
collector, provider adapter or infrastructure, compare the need against
`semantic_capability_entries` and `capability_entries` in
`FORGE_CONTEXT_PACKET`. Reuse or compose an accepted capability when sufficient;
state an exact named gap when missing; do not invent infrastructure under
uncertainty. Semantic entries never grant provider/data authority.

If isolated Critic context is unavailable, return typed `AUTO_HANDOFF_UNAVAILABLE`.
Do not silently self-criticize in the Forge context.

Slash does **not** authorize `apply-provenance-correction` or
`memory-policy-apply`. Read-only `inventory-placeholder-times` and
`memory-policy-status` / `memory-policy-preview` are also outside the slash
cycle. Memory-policy apply runs only after the slash ends, with
`--confirm-append-only`.

If the host platform mechanically requires command approval, request at most one
narrowly scoped batch at cycle start for
`uv run --locked --managed-python python -B scripts/hypothesis_forge.py ...`,
process-owned OS temp files, and append-only writes under the resolved canonical
RDP. Do not request broad shell/filesystem authority, a bare `python`
interpreter, unrestricted “Run Everything”, or user-level settings changes.

Hard boundaries — the slash does **not** authorize:

- Git mutation, branch, commit, PR or task creation
- Experiment execution or viewing new outcomes for ranking
- Untouched/forward holdout access
- Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash spend
- Deployment, promotion, or production strategy/bot execution
- Destructive RDP mutation, deletion, overwrite or restore
- A new capability atom
- Reopening a completed search on the same evidence+focus
- Autonomous Hypothesis Generator («magic ball»)

For `PASS_FAST_LANE_READY`, stop before experiment execution.
For `PASS_CHANGE_LANE_REQUIRED`, return one PRD+SSD and stop; do not create the PR.
For `PASS_DATA_OPTION_REQUIRED`, return the data option and stop; do not collect.

Allowed: read-only Git/Catalog navigation, bounded prior-work query, offline
commissioning when Fast Lane proof is absent and safe, design packets.

## Executable workflow

Happy path — no owner copy/paste between the slash command and the final terminal:

1. Run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py preflight --owner-focus <AUTO|text> --format json`.
   For the preregistered unchanged-representation CONTROL only, add
   `--control-current-representation` so the receipt carries
   `evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1`. Do not use this
   flag for ordinary Forge. CONTROL preflight stops with
   `CONTROL_YIELD_BELOW_MIN` or `CONTROL_CORPUS_UNRESOLVABLE` before creating a
   session when the imported live corpus yield is below
   `MIN_USABLE_YIELD_ELIGIBLE` or the corpus cannot be resolved from metadata.
2. Branch on `action`:
   - `RETURN_EXISTING_SESSION` → report `effective_control_terminal` when
     present, else `critic_terminal`, plus NEXT; stop. Do not treat primary C1
     `critic_terminal` as the CONTROL probe branch after F3 failover.
   - `RESUME_CRITIC` → use `critic_input_packet` from the preflight JSON
     (canonical frozen bytes); do not generate.
   - `RESUME_FINALIZE` → run finalize only.
   - `RESUME_REVISE` → `uv run --locked --managed-python python -B scripts/hypothesis_forge.py revise` (exactly one
     bounded revision), then isolated Critic again. Do not freeze a new search.
   - `RESUME_CLASSIFY` → `uv run --locked --managed-python python -B scripts/hypothesis_forge.py classify` with a
     schema-valid ExperimentSpec (network-free `classify_lane()`), then finalize.
     `PASS_TO_CLASSIFICATION` is not complete.
   - `STOP` → report the named terminal; stop.
     For `CONTROL_YIELD_BELOW_MIN`: show `control_yield_eligible` vs
     `min_usable_yield_eligible`; `OWNER NEXT=WAIT_FOR_IMPORT_OR_STOP`. Do not
     drop `--control-current-representation`. Do not recover by running general
     Forge. Do not freeze or launch Critic.
     For `CONTROL_CORPUS_UNRESOLVABLE`: `OWNER NEXT=STOP_CORPUS_UNRESOLVABLE`.
     Same recovery fence.
   - `START_NEW_SESSION` → continue.
3. Only for `START_NEW_SESSION`, run **PROMPT A** from the operator pack using
   `HFIC-V1.2` and only the bounded `FORGE_CONTEXT_PACKET` plus explicitly
   resolved evidence. In `CURRENT_REPRESENTATION_CONTROL_V1`, "explicitly
   resolved evidence" does **not** authorize reading raw current lifecycle
   observation rows, parquet observation bodies, per-mint raw trajectories,
   ordered raw lifecycle sequences, future `normalized_trajectory_v1` motifs,
   or any manually reconstructed equivalent of the challenger representation.
   CONTROL Prompt A may use the exact `FORGE_CONTEXT_PACKET`, its coarse
   dataset identities/fingerprints/labels, `feature_hints` / `feature_families`,
   `feature_grounding` projection, closed-family ledger, eligible prior memory
   under existing F2 rules, and ordinary Git/Catalog/operator truth required to
   interpret those IDs/contracts. General Forge read-only active-RDP navigation
   remains unchanged when the CONTROL flag is absent.
   Output a machine-valid `FORGE_DRAFT` with `packet_version=1.2`,
   `generator_prompt_version=HFIC-V1.2`, schema
   `catalog/schemas/hypothesis_forge_draft_v1_2.schema.json`.
   Do not emit `packet_version=1.1` or `HFIC-V1.1` on this fresh binding; freeze
   will fail closed with `FRESH_SESSION_DRAFT_VERSION_MISMATCH`.
   Copy `truth_roots_used`, `prior_work_receipts` and `research_memory_as_of` from
   preflight.    Do **not** emit `CRITIC_INPUT_PACKET`; freeze is the only packet builder.
   Prompt A search still uses only the bounded `ranked_prior_candidate_ids`
   shortlist; do not change candidate-generation strategy to recover omitted priors.
   Do **not** query prospects or include prospect IDs/research text in Prompt A.
4. Write machine `FORGE_DRAFT` to an OS temp file.
5. If Prompt A returned `NO_WORTHY_HYPOTHESIS` (empty `selected_candidate_ref`):
   - query `uv run --locked --managed-python python -B scripts/hypothesis_forge.py prospects --trigger POST_NO_WORTHY_REVIEW --max-results 3 --format json`;
   - run **PROMPT C** (`HFIC-NEXT-V1.0`) from the operator pack using only the
     already-bound `FORGE_CONTEXT_PACKET`, no-worthy portfolio, terminal, and
     at most three prospect summaries;
   - write a draft matching `hfic_next_epistemic_action_draft_v1.schema.json`;
   - one schema-repair attempt; if still invalid, omit `--next-action` so freeze
     persists deterministic `WAIT_FOR_NEW_EVIDENCE` / `NEXT_ACTION_GENERATION_FALLBACK`;
   - run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py freeze --draft <temp> --preflight-receipt <temp> --next-action <temp-or-omit> --format json`;
   - skip Independent Critic; do not finalize; report `NO_WORTHY_HYPOTHESIS` plus
     the typed next action. Proposed owner phrases are `PROPOSED_NOT_AUTHORITY`
     and must not be executed.
6. Otherwise run `uv run --locked --managed-python python -B scripts/hypothesis_forge.py freeze --draft <temp> --preflight-receipt <temp> --format json`.
   Frozen packet is authority. One schema-repair attempt, then `HFIC_PROTOCOL_INVALID`.
   Do not pass `--next-action` on a selected-candidate path.
   Fresh HFIC-V1.2 freeze emits critic `packet_version=1.4` with
   `generator_prompt_version=HFIC-V1.2`, freeze-owned selected-candidate
   grounding, and a complete bounded `prior_memory`
   snapshot of eligible historical `HYPOTHESIS_VERSION` records from the
   preflight-bound store **before** current session persist. Do not emit
   HFIC-V1.3 Prompt A. If freeze returns
   `PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED`: BLOCKED, not a crash; session was
   not written; do not launch Critic; do not paste a packet; do not retry the
   same slash expecting success. `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`.
   If freeze returns `PRIOR_MEMORY_RECORD_UNIDENTIFIED`: BLOCKED; session was
   not written; do not launch Critic. `OWNER NEXT=STOP_DO_NOT_LAUNCH_CRITIC`.
7. **Mandatory auto-handoff (selected path only):** launch Independent Critic in a new isolated context
   with only the frozen packet. Do not persist from Critic.
8. After critic returns `hypothesis_critic_result_v1`, branch on **which
   candidate this packet screened** and on `finalize` `session_state`:
   - Primary/C1 `REVISE_ONCE` only → `finalize` persists `REVISION_REQUIRED`;
     then `revise` (one claim-wording repair); then isolated Critic again;
     second terminal must be PASS/KILL, never a second `REVISE_ONCE`.
   - `PASS_TO_CLASSIFICATION` → `finalize` persists `AWAITING_CLASSIFICATION`;
     then `classify`; then finalize. This is not a completed terminal.
   - Primary/C1 `KILL_*` → `finalize`. If `session_state=RUNNER_UP_AWAITING_CRITIC`,
     do **not** emit `SYNTHESIS_COMPLETE` and do **not** mark the evening done.
     Same slash: launch Critic #2 in a **new** isolated context with **only**
     the pre-frozen C2 packet (`RESUME_CRITIC` `critic_input_packet` or freeze
     `runner_up_critic_input_packet`). Then `finalize` the C2 result.
   - C2 `REVISE_ONCE` → `finalize` persists `PAUSE` / `RUNNER_UP_REVISION_REQUIRED`.
     Do **not** run `revise`. No C3. No new search.
   - PASS/OWNER/DATA/CHANGE on C1 never launches runner-up Critic.
   Fake/nonempty classifier objects are invalid. Final `PASS_*` requires a live
   network-free classifier receipt bound to session/selected/spec hash.
9. Verify `SYNTHESIS_COMPLETE` / RDP receipt, Git mutation 0, provider calls 0
   before telling the owner the cycle is complete.
10. On crash/retry, resume; never regenerate the same evidence+focus search.

## Mandatory auto-handoff (non-negotiable)

Forge is **not complete** when the packet is printed. The owner must not need to
remember step 2.

Immediately after a valid frozen `CRITIC_INPUT_PACKET` (selected path only):

1. Emit a synthesis handoff receipt with `synthesis_status: PENDING_CRITIC` per
   `catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json` (v1.0
   readers remain valid for historical fixtures).
2. **Launch Independent Critic in a new isolated context** using `Task`
   subagent, `.agents/skills/independent-hypothesis-critic/SKILL.md`, and
   **only** the packet (no Forge narrative, no intermediate reasoning, no
   ResearchStore walk). Fresh critic `packet_version=1.4` already carries
   complete prior memory and freeze-owned grounding. Do not reconstruct
   `prior_memory` for historical `1.2`. Do not reconstruct packet 1.4 grounding
   from Catalog/RDP. Historical `packet_version=1.3` remains readable.
   If isolated context cannot launch, return typed `AUTO_HANDOFF_UNAVAILABLE`
   and STOP. Do not instruct the owner to open a new chat, paste the packet,
   or press Run. Do not silently self-criticize in the Forge context.
3. Do not mark the evening cycle done, do not propose execution tasks, and do not
   treat synthesis as finished until `finalize` has persisted `SYNTHESIS_COMPLETE`.
   Primary `KILL_*` that returns `RUNNER_UP_AWAITING_CRITIC` is **not** complete:
   launch Critic #2 first. C2 `REVISE_ONCE` completes as `PAUSE` /
   `RUNNER_UP_REVISION_REQUIRED` with `OWNER NEXT=STOP` — no `revise`, no C3,
   no new AUTO search, no candidate shopping.
4. After `finalize` returns `session_state=SYNTHESIS_COMPLETE`, emit handoff with
   `synthesis_status: SYNTHESIS_COMPLETE`,
   `critic_terminal`, `critic_report_present: true`, and when the final terminal is
   post-classification (`PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`,
   `PASS_DATA_OPTION_REQUIRED`): `classifier_receipt_present: true` plus
   `lane_classifier_terminal` from offline `classify_lane()`. `PASS_*` is readiness
   / `PAUSE`, never promotion or alpha.

   The v1.1 synthesis handoff schema is `additionalProperties: false` and cannot
   carry v1.3 `final_session_terminal` / `runner_up_critic_terminal`. On runner-up
   failover, read those fields from the session receipt / `show_session`, not from
   the v1.1 handoff. Legacy handoff `critic_terminal` stays the C1 primary KILL for
   v1.2 identity and is **not** the evening scientific result. Do not claim C1
   KILL as C2's outcome. Do not put C2's classifier lane on C1-bound
   `lane_classifier_terminal`.

If packet validation fails, return `STATUS=NOT_READY`, keep
`synthesis_status: FORGE_NOT_READY`, and one repair action. Do not launch critic
on an invalid packet.

## Output contract

Speak to the owner in Russian. Keep schemas, enums, packet fields and paths
canonical in English.

Never end with a conditional backlog. One execution unit maximum per cycle.
KILL/STOP is a complete useful result. Primary `KILL_*` plus pending C2 screen
is not evening-complete. C2 `RUNNER_UP_REVISION_REQUIRED` is a typed PAUSE STOP,
not a prompt to shop another candidate or start a second AUTO search.

## Model effort

Use `SOL_XHIGH` for mechanism/PIT/estimand reasoning. Critic handoff may use the
same or a different strong model; isolation matters more than model identity.
