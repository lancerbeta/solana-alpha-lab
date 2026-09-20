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

## Real C1/C2 no-write acceptance

persist=False against this machine's LIVE CORPUS instance.

- CONTROL session `HFIC-SESS-4F80F1151844EC1B`
- effective BASE terminal `NO_WORTHY_HYPOTHESIS`
- next_action **START_V1** (not SEARCH_EXHAUSTED, not Prompt C WAIT)
- owner_final **null**; readout `status: NEXT — continue V1 envelope; do not treat WAIT as done`
- visible cohorts: `REL-20260902T111900Z-20260909T111900Z`,
  `REL-20260909T111900Z-20260916T111900Z`
- BASE used cohorts: same two visible CONTROL cohorts
- V1 used cohorts: none (`NOT_RUN`, `REPRESENTATION_RELEASE_LOCAL`)
- legacy epoch `456411903174e403092f115cddf62fd38c9ae1bb943ebba0048c5b6bd070854e`
- forge_run_receipt_sha256 `6e53798db0636c0766907a5781f6e76888059924e7880118e2f0146e7e2aa24a`
- store inventory unchanged; writes: research_store 0, forge_run 0, session 0

Do not commit current runtime outputs or absolute machine paths.

## Fixture routing (disposable plane)

Stub generator/Critic answers. Real freeze/finalize, A3 input binding,
resolver, persist/readback, V1 challenger envelope, and owner rendering:

- Resolver: PASS BASE candidate skips V1; freeze+finalize `KILL_MECHANISM` does not start V1
- CONTROL NO_WORTHY persist → START_V1
- Empty-BASE V1 envelope is CONTROL `FORGE_CONTEXT_PACKET` via
  `consume_start_v1_envelope`: no fake critic packet (`critic_input_packet`
  is null); compact representation is a sibling on the dormant challenger.
  Selected-candidate CONTROL still uses the existing HFIC lifecycle seam
  where the critic packet stays the CONTROL clone.
- Visible C1+C2 are not V1 used cohorts
- Later known handler via registry; unknown ACTIVE id fail-closes
- Two worktrees resolve one data root; synthetic C3 changes the input
  snapshot without ladder YAML edits; historical A3 C1/C2 evidence bytes
  unchanged

## What did not change

No Prompt A/B/C on market evidence, no Independent Critic on a real
hypothesis, no V1 scientific probe, no new market epoch, no A5
identity/gold, no historical receipt rewrite, no provider/VPS.

A4 local idempotency is exact frozen run/CONTROL slot. Budget stability
across later Git changes is A5.

## Residual

Named consumer after merge/readback: A5 identity/provenance + owner gold.
`CAPABILITY_RADAR_NOW=NONE`. STOP before owner merge phrase.
