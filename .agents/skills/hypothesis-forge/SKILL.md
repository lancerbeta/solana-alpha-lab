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

Hard boundaries — zero tolerance:

- Git mutation, branch, PR, task or evidence file creation
- Experiment execution or viewing new outcomes for ranking
- Untouched/forward holdout access
- Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash spend
- Autonomous Hypothesis Generator («magic ball»)

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
2. **Launch Independent Critic in a new isolated context** using one of:
   - `Task` subagent with read-only critic instructions and **only** the packet
     (no Forge narrative, no intermediate reasoning); or
   - instruct the owner to open a **new chat** and run `/independent-hypothesis-critic`
     with the packet — only if subagent launch is unavailable.
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
