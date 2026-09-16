# HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1 — Owner readout

Date: 2026-09-16 · Route: DIRECT_CURSOR_DELIVERY · Terminal: `HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_PASS` (pending merge)

Pinned real-state AFTER: `docs/evidence/hfic_forge_prior_context_capacity_repair/a1_active_rdp_preview_v1.json`

## Measured dead-end (real local RDP)

- cohort: `REL-20260902T111900Z-20260909T111900Z`
- evidence epoch: `ba8844147733e4421c2b497b7e70d23f20a22afa95f76e84f6beb3aff753effc`
- completed CONTROL: `HFIC-SESS-60FB3DA7C8EB33FC` (still search-memory eligible; not quarantined)
- focus under test: `IDENTIFIABLE_NOW`

### BEFORE (Critic-grade capsule reused for Prompt A)

| Metric | Value |
| --- | --- |
| ranked prior count | 8 (dropped_priors=1 honest) |
| ranked prior bytes | 9298 |
| total packet bytes | >16384 after semantic/feature-grounding compaction |
| terminal | capacity overflow (historically mislabeled `RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE`; with this patch the same shape raises `FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED`) |

### AFTER (Forge projection + duplicate recipe cleanup)

| Metric | Value |
| --- | --- |
| ranked prior count | 8 |
| ranked prior bytes | 4431 |
| total packet bytes | 16045 |
| vision | PASS (feature grounding retained; semantic dropped via existing compaction) |
| expected preflight action | `START_NEW_SESSION` |
| fits_bound | true |
| one_to_one | true |

## Invariants confirmed

- 60FB quarantine status unchanged (`quarantine_marker=null`)
- search-memory eligibility unchanged
- Critic `prior_memory` / `compact_prior_entry` semantics unchanged
- distinct-focus budget unchanged (1/3 used; AUTO exhausted; 2 remain)
- representation gate unchanged (`INVALID_CASE_C_OBSERVABILITY` still blocks challenger)
- no real `/hypothesis-forge IDENTIFIABLE_NOW` session executed in this atom

## What changed

1. `compact_forge_prior_entry` for Prompt A ranked bodies (Critic-rich fields only as fallback distinguishers)
2. `FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED` distinct from missing-body
3. Removed duplicate `related_prior_recipe_ids` and ranked IDs from `prior_work_receipts` (permanent AUDIT_ONLY de-dupe)
4. Source-only usefulness gate so lean projection cannot mislabel as `RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE`

## Non-claims

Not alpha. Not representation eligibility. Not permission to run IDENTIFIABLE_NOW inside this PR.
