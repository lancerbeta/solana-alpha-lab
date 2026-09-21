# A5 owner readout — FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1

## Owner status

| Status | Meaning |
|---|---|
| **DONE** (atom delivery) | admission → lifecycle → occupancy → readback vertical on production freeze/Critic/classify/list/discovery bindings |
| **STOP** | merge only after exact-head CI + merge-readiness + machine-rendered owner phrase. This readout is not merge authority |
| **NEXT** (after merge, separate OK) | authorized `/hypothesis-forge` on current evidence — not in this atom |

## Live no-write first-run (C1/C2)

Evidence: `docs/evidence/forge_evidence_identity_and_owner_gold/a1_no_write_c1_c2_disposition_v1.json`

- First-run action: `START_BASE` + `CONTROL_SURFACE_REQUIRED`
- Inventory unchanged; `scientific_writes=0`
- Stamp-only budget for the **current** market: unstamped legacy does not occupy
  current quota. List/load may restore stamps from earlier freeze cycles of the
  same session so a completed look does not lose occupancy after Critic/classify.
  That restore is not “missing stamp still counts as free.”

## Owner blocks (START / RESUME / REUSED / BLOCKED)

| Situation | Owner signal |
|---|---|
| Declared input matches occupied slot | `RESUME` / `RETURN_EXISTING` — same trial; do not start a second |
| Same market, completed PASS | `REUSED_VALID` / `OWNER_CANDIDATE` readback — historical answer for **this** input |
| New cohort / new market (e.g. C3 after C1+C2 PASS) | `START_BASE` (or next registered representation) — stale PASS is historical only |
| Git/docs-only or capability-only change | Does **not** free market budget; occupied slot remains |
| Incomplete market | `BLOCKED` / `MARKET_EVIDENCE_BASIS_INCOMPLETE` — restore input first; not a scientific negative |
| Restart mid-Critic / mid-classify | `RESUME` same session; draft bytes remain addressable |

## Whole-path counters (production APIs)

| Phase | market stamp on listed session | budget occupancy |
|---|---|---|
| after freeze | present | ≥1 |
| after `PASS_TO_CLASSIFICATION` | present | ≥1 |
| after classification complete + fresh store open | present | ≥1 |
| after C3 import | prior session historical | new market starts fresh search |

## Non-claims

- No scientific market Forge / Prompt A–C / real Critic
- No A6, provider/VPS, historical rewrite, quota expansion
- Fixture gold ≠ alpha
- Merge requires separate machine-rendered A5 owner phrase after readiness
