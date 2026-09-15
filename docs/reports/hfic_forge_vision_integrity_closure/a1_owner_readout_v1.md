# HFIC_FORGE_VISION_INTEGRITY_CLOSURE_V1 — Owner Readout

Date: 2026-09-15 · Route: DIRECT_CURSOR_DELIVERY · Terminal: ready for PR

## What closed (3 root causes, one causal chain, one PR)

1. **Positive suppression authority** (`hfic_suppression_semantics.py`):
   `*_FAMILY` naming / `family_close` flag alone can never hard-close a
   family. Family close requires positive typed authority: scientific result
   actually ran, exact scope identity, population/estimand context,
   hash-bound source. Legacy quote-retention close now stays
   `SCIENTIFIC_CLOSE_VALID` only from its confirmatory source; the
   `design_probe.science=false` legacy source is no longer authority.
   Owner parks suppress nothing; scope-limited closes cannot widen.

2. **Machine vision integrity** (`hfic_vision_integrity.py` + preflight +
   session): every packet carries a `vision_integrity` receipt; every omitted
   feature/grounding/semantic/capability item is deterministically classified
   `REDUNDANT_WITH_RETAINED_INFORMATION` or
   `INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION`. Material/unknown omission ⇒
   typed `FORGE_VISION_INTEGRITY_BLOCKED`. `NO_WORTHY_HYPOTHESIS` (and the
   selected-candidate freeze) cannot persist unless vision integrity = PASS.
   Packet compaction (family-level availability index + compact semantic
   entries + deduped family rows) keeps the real C1 packet at **15913 bytes**
   ≤ 16384 with vision PASS.

3. **Challenger runtime seam** (`hfic_released_trajectory_projection.py` +
   probe fix): a verified imported live-cohort release now resolves through
   the canonical path — release/source/census/observations/schedule/activation
   hashes verified, member anchors from the census admission field, PIT
   cutoffs frozen, missingness stays M, no mint identity. Proven on the real
   imported release `REL-20260902T111900Z-20260909T111900Z`:
   78080 observation rows → 29280 projected typed observations,
   yield_eligible=148, receipt `VERIFIED`. Terminal
   `NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED` — no challenger
   execution, no motif materialization in this atom.

## Real C1 read-only acceptance

`vision-acceptance` (new read-only CLI) over `local/factory_v1/data_plane`
plus the real imported release:

- SUPPRESSION: not_portable_as_hard_close=0, ambiguous=0, parks=0,
  scope_overclosure=0; 6 portable family hard-closes with POSITIVE authority.
- PRIORS: H11+H13 visible/body/ranked, mismatch=0, dropped=0.
- VISION: material_information_loss=0, unknown_omission=0, status PASS.
- PACKET/CONTROL: 15913 ≤ 16384 bytes, trajectory-blind, no raw leak,
  planned action START_NEW_SESSION, yield gate OK (148).
- CALIBRATION: defective session HFIC-SESS-8F4A703030408365 is the exact
  planned quarantine; post-state has no undesired calibration HFIC memory.
- CHALLENGER: seam VERIFIED on the real release; no future Git atom needed.

Terminal: **FORGE_VISION_ACCEPTANCE_PASS**
(evidence: `docs/evidence/hfic_forge_vision_integrity_closure/a1_real_c1_vision_acceptance_v1.json`).

## Post-merge C1 operation (one-person, no Git)

1. `preview-reopened-prior-routing` (read-only, idempotent — tested)
2. owner-authorized `commission-reopened-priors --confirm-append-only`
   (append-only, repeat-safe — tested)
3. `vision-acceptance` machine readback → PASS
4. `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`
5. if terminal permits: NORMALIZED_TRAJECTORY_V1 executes through the merged
   seam — no new PR.

## Factory fit

- Git needed for C2+ routine Forge? **No.**
- Owner maintains a suppressor list? **No.**
- Future packet growth silently causing NO_WORTHY? **No** — typed
  FORGE_VISION_INTEGRITY_BLOCKED instead.
- Legacy CLOSE name alone can suppress? **No.**
- Ranked prior without body? **No.**
- New service/DB? **No.**
- Corrected C1 needs only one append-only commissioning gate before slash?
  **Yes.**
- CONTROL→NORMALIZED_TRAJECTORY_V1 needs another code PR? **No.**
- Data deficiencies surface as typed evidence terminals, not crashes?
  **Yes.**

## Tests

New: suppression positive authority (9), vision integrity (5), released
trajectory projection (5), vision acceptance operations (4).
Regression: preflight/session/CLI (54), reopened prior routing + legacy
science rebase + control integrity (45+), representation probe. All green.
