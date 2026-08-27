---
name: hypothesis-forge
description: Manual Hypothesis Forge for Solana Alpha Lab under MANUAL_FALLBACK_UNTIL_GENERATOR. Use only when the owner explicitly invokes /hypothesis-forge. Runs executable preflight → freeze → isolated Critic → optional revise/classify → finalize. No Git mutation, provider calls, experiment execution or autonomous generator.
---

# Hypothesis Forge

Use **only** when the owner explicitly invokes `/hypothesis-forge`. Do not run Forge
from orientation, autonomous delivery, or implicit continuation phrases.

Manual hypothesis synthesis contour for Solana Alpha Lab while
`MANUAL_FALLBACK_UNTIL_GENERATOR` remains active. Prompt version `HFIC-V1.1`.

Canonical entrypoint: `scripts/hypothesis_forge.py`.

## Authority

Read `configs/hypothesis_forge_independent_critic_v1.yaml` and the operator pack at
`docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`.

One explicit `/hypothesis-forge` is scoped authorization for exactly one HFIC
session (`ONE_SLASH_ONE_SESSION`), expiring at final terminal/STOP.
`ZERO_MID_CYCLE_OWNER_INTERVENTION`: do not ask the owner to press Run or
approve an RDP write between preflight, freeze, Critic, revision/classification
and finalize. `PASS_TO_CLASSIFICATION` and exactly one bounded `REVISE_ONCE`
remain inside the original slash authority and continue automatically.

Authorized without additional owner questions: read-only Git/Catalog/active RDP
navigation; preflight and safe offline commissioning on the same canonical data
root if genuinely required; process-owned OS temp files; append-only RDP writes
for context artifact, session/cycle, all candidate versions, frozen Critic
packet, Critic result, revision receipt, classifier receipt, decisions, session
receipt and terminal; automatic isolated Critic handoff; network-free
deterministic lane classification; finalize; replay/resume/`prove-runtime`;
cleanup of process-owned temp files.

If isolated Critic context is unavailable, return typed `AUTO_HANDOFF_UNAVAILABLE`.
Do not silently self-criticize in the Forge context.

Slash does **not** authorize `apply-provenance-correction`. Read-only
`inventory-placeholder-times` is also outside the slash cycle and runs only
after the exact owner merge phrase.

If the host platform mechanically requires command approval, request at most one
narrowly scoped batch at cycle start for `python -B scripts/hypothesis_forge.py ...`,
process-owned OS temp files, and append-only writes under the resolved canonical
RDP. Do not request broad shell/filesystem authority, unrestricted “Run
Everything”, or user-level settings changes.

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

1. Run `python -B scripts/hypothesis_forge.py preflight --owner-focus <AUTO|text> --format json`.
2. Branch on `action`:
   - `RETURN_EXISTING_SESSION` → report the stored terminal/NEXT; stop.
   - `RESUME_CRITIC` → use `critic_input_packet` from the preflight JSON
     (canonical frozen bytes); do not generate.
   - `RESUME_FINALIZE` → run finalize only.
   - `RESUME_REVISE` → `python -B scripts/hypothesis_forge.py revise` (exactly one
     bounded revision), then isolated Critic again. Do not freeze a new search.
   - `RESUME_CLASSIFY` → `python -B scripts/hypothesis_forge.py classify` with a
     schema-valid ExperimentSpec (network-free `classify_lane()`), then finalize.
     `PASS_TO_CLASSIFICATION` is not complete.
   - `STOP` → report the named terminal; stop.
   - `START_NEW_SESSION` → continue.
3. Only for `START_NEW_SESSION`, run **PROMPT A** from the operator pack using
   `HFIC-V1.1` and only the bounded `FORGE_CONTEXT_PACKET` plus explicitly
   resolved evidence. Display ordinals are display-only; do not invent canonical IDs.
   Output a machine-valid `FORGE_DRAFT` (`hypothesis_forge_draft_v1.schema.json`).
   Copy `truth_roots_used`, `prior_work_receipts` and `research_memory_as_of` from
   preflight. Do **not** emit `CRITIC_INPUT_PACKET`; freeze is the only packet builder.
4. Write machine `FORGE_DRAFT` to an OS temp file.
5. Run `python -B scripts/hypothesis_forge.py freeze --draft <temp> --preflight-receipt <temp> --format json`.
   Frozen packet is authority. One schema-repair attempt, then `HFIC_PROTOCOL_INVALID`.
6. **Mandatory auto-handoff:** launch Independent Critic in a new isolated context
   with only the frozen packet. Do not persist from Critic.
7. After critic returns `hypothesis_critic_result_v1`:
   - `REVISE_ONCE` → `python -B scripts/hypothesis_forge.py finalize` persists
     `REVISION_REQUIRED`; then `python -B scripts/hypothesis_forge.py revise`
     (one claim-wording repair); then isolated Critic again; second terminal
     must be PASS/KILL, never a second `REVISE_ONCE`.
   - `PASS_TO_CLASSIFICATION` → `python -B scripts/hypothesis_forge.py finalize`
     persists `AWAITING_CLASSIFICATION`; then
     `python -B scripts/hypothesis_forge.py classify`; then finalize. This is
     not a completed terminal.
   - `KILL_*` / `NO_WORTHY_HYPOTHESIS` → `python -B scripts/hypothesis_forge.py finalize`.
   Fake/nonempty classifier objects are invalid. Final `PASS_*` requires a live
   network-free classifier receipt bound to session/selected/spec hash.
8. Verify `SYNTHESIS_COMPLETE` / RDP receipt, Git mutation 0, provider calls 0
   before telling the owner the cycle is complete.
9. On crash/retry, resume; never regenerate the same evidence+focus search.

## Mandatory auto-handoff (non-negotiable)

Forge is **not complete** when the packet is printed. The owner must not need to
remember step 2.

Immediately after a valid frozen `CRITIC_INPUT_PACKET`:

1. Emit a synthesis handoff receipt with `synthesis_status: PENDING_CRITIC` per
   `catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json` (v1.0
   readers remain valid for historical fixtures).
2. **Launch Independent Critic in a new isolated context** using `Task`
   subagent with read-only critic instructions and **only** the packet
   (no Forge narrative, no intermediate reasoning).
   If isolated context cannot launch, return typed `AUTO_HANDOFF_UNAVAILABLE`
   and STOP. Do not instruct the owner to open a new chat, paste the packet,
   or press Run. Do not silently self-criticize in the Forge context.
3. Do not mark the evening cycle done, do not propose execution tasks, and do not
   treat synthesis as finished until the critic returns one terminal and one NEXT
   and `finalize` has persisted them.
4. After critic returns, emit handoff with `synthesis_status: SYNTHESIS_COMPLETE`,
   `critic_terminal`, `critic_report_present: true`, and when the final terminal is
   post-classification (`PASS_FAST_LANE_READY`, `PASS_CHANGE_LANE_REQUIRED`,
   `PASS_DATA_OPTION_REQUIRED`): `classifier_receipt_present: true` plus
   `lane_classifier_terminal` from offline `classify_lane()`. `PASS_*` is readiness
   / `PAUSE`, never promotion or alpha.

If packet validation fails, return `STATUS=NOT_READY`, keep
`synthesis_status: FORGE_NOT_READY`, and one repair action. Do not launch critic
on an invalid packet.

## Output contract

Speak to the owner in Russian. Keep schemas, enums, packet fields and paths
canonical in English.

Never end with a conditional backlog. One execution unit maximum per cycle.
KILL/STOP is a complete useful result.

## Model effort

Use `SOL_XHIGH` for mechanism/PIT/estimand reasoning. Critic handoff may use the
same or a different strong model; isolation matters more than model identity.
