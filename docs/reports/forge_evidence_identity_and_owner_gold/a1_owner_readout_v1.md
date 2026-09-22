# A5 owner readout — FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1

## Owner status

| Status | Meaning |
|---|---|
| **DONE** (atom delivery) | admission → lifecycle → occupancy → readback vertical is wired through production freeze/Critic/classify/list/discovery bindings |
| **STOP** | merge only after exact-head CI + merge-readiness + the machine-rendered owner phrase; this readout is not merge authority |
| **NEXT** (after merge, separate OK) | authorized `/hypothesis-forge` on current evidence — not part of this atom |

## Live no-write first-run (C1/C2)

Evidence: `docs/evidence/forge_evidence_identity_and_owner_gold/a1_no_write_c1_c2_disposition_v1.json`

- `forge-input`: `FORGE_INPUT_READY`, `STOP_BEFORE_SYNTHESIS`, receipt
  `d6d1748e9b7b69d8a8b71a65fc475d91b0fcab4c3a5fb58b406a83b6c46b4b91`.
- `preflight`: planned action `START_NEW_SESSION`, selection
  `SINGLE_COMMISSIONED`, router `BLOCK_FORGE_SELECTION_RISK`; this is a
  selection-robustness routing block, not a scientific negative and not
  permission for a real run. Receipt:
  `c84091ad59d8f67cf22a97c2beb81fc092580b7c5bc585fdddc6fc2bcea47612`.
- Current market identity:
  `3792e874db5a0af2082fc0fe9fbd37a02a7aa55f4b1505f9366064c0d5fee2a9`.
  Capability identity:
  `0b2626a359495f97785fa3240e6237e633de717665e93525ea1178f15f506e55`;
  changing capability does not free the market budget.
- Inventory is unchanged (`defbc9a5a1794b05` before and after); the read-only
  path reports `scientific_writes=0`, 17 readable sessions, 2 historical
  CONTROL rows, and zero current-market occupancy.

## Owner blocks (START / RESUME / REUSED / BLOCKED)

| Situation | Owner signal |
|---|---|
| Declared input matches an occupied current slot | `RESUME_BASE` / `RESUME_V1` / `RETURN_EXISTING` — same trial; do not start a second |
| Same market, completed PASS with valid current slot and binding | `REUSED_VALID` / `OWNER_CANDIDATE` — historical answer for this exact input |
| Market-stamped row has no readable scientific slot | `BLOCKED` / `SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING` — restore/read back the production record; do not treat the slot as free |
| Legacy row has no verifiable current market stamp | `HISTORICAL_ONLY` or `UNRESOLVED_BINDING` — readable history, not current occupancy, with no historical rewrite |
| New cohort / new market (for example C3 after C1+C2 PASS) | `START_NEW_SESSION` — stale PASS is historical only |
| Fresh ordinary BASE on the live C1/C2 path | `START_NEW_SESSION` plus `BLOCK_FORGE_SELECTION_RISK` until the selection gate is resolved; not a scientific negative |
| Git/docs-only or capability-only change | Does **not** free market budget; an incompatible completed execution is not silently reused |
| Incomplete market | `BLOCKED` / `MARKET_EVIDENCE_BASIS_INCOMPLETE` — restore input first |
| Restart mid-Critic / mid-classify | `RESUME_BASE` / `RESUME_V1` same session; draft bytes and occupancy remain addressable |

## Whole-path counters (production APIs)

| Phase | market stamp / slot readback | budget occupancy |
|---|---|---|
| after freeze | market + slot readback; execution binding is `VERIFIED` only when all model/payload/memory provenance is present, otherwise durable `UNKNOWN` | ≥1 |
| after `PASS_TO_CLASSIFICATION` | same identity fields remain present; no missing provenance is upgraded by classification | ≥1 |
| after classification complete + fresh store open | durable readback is preserved, including explicit `UNKNOWN` where provenance is incomplete | ≥1 |
| after restart | same session and draft bytes | occupied slot does not disappear |
| after C3 import | prior session is historical for C3 | new market gets a separate search decision |

## Non-claims

- No scientific market Forge / Prompt A–C / real Critic
- No A6, provider/VPS, historical rewrite, science or quota expansion
- Fixture gold is not alpha and production bindings are not replaced by fixture results
- Merge requires the separate machine-rendered A5 owner phrase after readiness
