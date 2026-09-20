# FORGE_REPRESENTATION_LADDER_V1 — Owner readout

Date: 2026-09-20 · Route: DIRECT_CURSOR_DELIVERY

Program: fourth atom of owner-path convergence. A5 identity/gold and a real
scientific `/hypothesis-forge` are not this atom.

## What changed

One `/hypothesis-forge` is now a bounded Forge **run**
(`ONE_SLASH_ONE_BOUNDED_RUN`), not a single HFIC session. Machine path:

`forge-input` (A3) → `forge-run` resolver → existing freeze/finalize/Critic.

`evaluate_forge_run` returns one `smial.forge-run-receipt` 1.0 with stage
refs, visible vs used cohorts, one `next_action`, and one owner-final when
the allowed search is complete. Prompt C historical WAIT is not owner-final
while V1 remains eligible: CONTROL `NO_WORTHY` + V1 ACTIVE auto-advances to
`START_V1` without an owner "continue". Session `RETURN_EXISTING_SESSION`
does not stop that run. The owner result is `owner_readout` (`FORGE RUN`),
not the raw JSON dump. Repeat slash on a completed run is
`RETURN_EXISTING_RUN`. A3 remains the only input/visibility owner.

Normal `forge-run` no longer defaults to historical CONTROL
`HFIC-SESS-4F80F1151844EC1B`. BASE is reused only when owner-focus and bound
cohorts match the current A3 evidence set; `used_cohort_ids` come from the
session packet, not current visible. V1/later stages are read from persisted
HFIC sessions; aggregate receipts append on real progress; a completed run
readback is `RETURN_EXISTING_RUN`. A later ACTIVE representation is consumed
when its stage exists; it is not restarted with another `START_*`.

## Real C1/C2 no-write acceptance

persist=False against this machine's LIVE CORPUS instance. Explicit historical
lookup of CONTROL `HFIC-SESS-4F80F1151844EC1B` remains a fixture/compatibility
path, not the normal default.

- CONTROL session `HFIC-SESS-4F80F1151844EC1B`
- effective BASE terminal `NO_WORTHY_HYPOTHESIS`
- next_action **START_V1** (not SEARCH_EXHAUSTED, not Prompt C WAIT)
- owner_final **null**; readout `status: NEXT — continue V1 envelope; do not treat WAIT as done`
- visible cohorts: `REL-20260902T111900Z-20260909T111900Z`,
  `REL-20260909T111900Z-20260916T111900Z`
- V1 used cohorts: none (`NOT_RUN`, `REPRESENTATION_RELEASE_LOCAL`)
- legacy epoch `456411903174e403092f115cddf62fd38c9ae1bb943ebba0048c5b6bd070854e`
- store inventory unchanged; writes: research_store 0, forge_run 0, session 0

Do not commit current runtime outputs or absolute machine paths.

## Fixture routing (disposable plane)

Stub generator/Critic answers. Dataset/packet binding, freeze/finalize,
resolver, persist/readback, and owner rendering are real:

| Scenario | Result |
|---|---|
| F1 fresh plane, matching C1+C2 CONTROL, no magic session id | BASE `REUSED_VALID`, used C1+C2, `START_V1` |
| F1 same CONTROL after synthetic C3 / other focus | used does not gain C3; not `REUSED_VALID` over new evidence; other focus → `START_BASE` |
| F2 empty BASE → stub V1 candidate → freeze/finalize → `forge-run` | `OWNER_CANDIDATE`; V1 session_id + stage ref resolve; retry `RETURN_EXISTING_RUN` |
| F2 empty BASE → stub V1 no-worthy → `forge-run` | scoped `SEARCH_EXHAUSTED_CURRENT_EVIDENCE`; retry readback |
| F2 CONTROL vs V1 freeze slot | same epoch/focus lookup returns BASE for BASE slot and V1 for V1 slot |
| F2 CLI `ladder_freeze_preflight` → `freeze_draft(store=)` | V1 session_id distinct from CONTROL; no `START_NEW_SESSION` bind |
| F2 orphan V1 without parent | not bound to current CONTROL; next remains `START_V1` |
| F2 incomplete persist → saved V1 draft → terminal | append-only progress; no second trial |
| F3 V1 no-worthy + completed synthetic V2 | `OWNER_CANDIDATE`, not `START_SYNTHETIC_LATER_V2`; retry readback |
| F3 completed V2 with foreign parent | not consumed; `START_SYNTHETIC_LATER_V2` |
| Visible vs used | V1 used release-local C2; not all visible C1+C2 |
| Two worktrees + C3 | one data root; historical A3 C1/C2 evidence bytes unchanged |

Empty-BASE V1 envelope remains CONTROL `FORGE_CONTEXT_PACKET` via
`consume_start_v1_envelope` (no fake critic; challenger tagged
`ladder_representation_id=NORMALIZED_TRAJECTORY_V1`). Freeze uses
`ladder_freeze_preflight`, not the CONTROL preflight. `cmd_freeze` /
`freeze_draft(store=)` consumes that object (loads CONTROL packet from digest,
skips `START_NEW_SESSION` bind). After freeze/finalize,
re-run `forge-run` to read artifacts. Ordinary `CONTROL_REQUIRED` is
`status: DONE` (expert CONTROL slash is not owner NEXT). Unknown ACTIVE handler still fail-closes.
Owner readout prints candidate/declined/critic identity from artifacts.

## What did not change

No Prompt A/B/C on market evidence, no Independent Critic on a real
hypothesis, no V1 scientific probe, no new market epoch, no A5
identity/gold, no historical receipt rewrite, no provider/VPS.

A4 local idempotency is exact frozen run/CONTROL slot. Budget stability
across later Git changes is A5.

## Residual

Named consumer after merge/readback: A5 identity/provenance + owner gold.
`CAPABILITY_RADAR_NOW=NONE`. STOP before owner merge phrase.
Previous PR #328 head `9997e8dc…` is not this candidate.
