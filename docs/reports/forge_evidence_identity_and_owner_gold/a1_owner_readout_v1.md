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
  `f12262b60c4074de40993ae19479cf02d3e165598dfea0193b9965473ec7d198`;
  exact no-write Git head `237b2bc7e13e6d186a6f66a3aed93401fd70b451`.
- `preflight`: planned action `START_NEW_SESSION`, selection
  `SINGLE_COMMISSIONED`, router `BLOCK_FORGE_SELECTION_RISK`; the gate is a
  scoped historical caveat (`caveat=true`, `full_lifecycle_equivalent=false`),
  not a scientific negative and not permission for a real run. The production
  next is `CONTINUE_WITH_SCOPED_SELECTION_CAVEAT` for the canonical no-write
  Forge/readback path; if the gate returns a typed STOP, the CLI next is
  `RESOLVE_SELECTION_GATE` and it must not create a trial. Receipt:
  `f31f27e6adaada036a1256309992af0dc1a485ccd02821a6230297cf3ee0faf4`.
- The direct no-write forge-run readback is `START_BASE` with
  `CONTROL_SURFACE_REQUIRED`, scientific slot
  `212149f7d9afdcffa3dc7a0df69f8f53bea0af080722c4f2cc5cc05813a5299c`,
  receipt `26af73d14a391a411190facc0ce3808d5a148235a0249ffeb732d78444bd7ab1`,
  and `research_store=0 forge_run=0 session=0 forge_context=0`.
- Current market identity:
  `3792e874db5a0af2082fc0fe9fbd37a02a7aa55f4b1505f9366064c0d5fee2a9`.
  Capability identity:
  `9ac25552c72899523c17cc45d7bd8a1b100c6942634fb6bb185e0b484e1444bc`;
  the code-only head change altered capability identity while market identity
  and budget remained unchanged.
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

The following are numeric counters from the disposable production-path owner
gold (G6/G8), not a scientific run and not manually stamped fixtures:

| Checkpoint | `auto_sessions_used` | `distinct_focus_used` | representation slots | current-market occupancy | readback next |
|---|---:|---:|---:|---:|---|
| generated draft / freeze | 1 | 0 | 1 | 1 | `RESUME_EXISTING_SESSION` |
| after `PASS_TO_CLASSIFICATION` | 1 | 0 | 1 | 1 | same slot |
| fresh-store completion readback | 1 | 0 | 1 | 1 | `RETURN_EXISTING` |
| restart before freeze completion | 1 | 0 | 1 | 1 | `RESUME_BASE` / `RESUME_V1` |
| C3 import after old PASS | 0 for new market | 0 | 0 current; 1 historical | 0 current; old slot retained | `START_BASE` |

Readback calls in the restart and replay rows have
`research_store=0`, `forge_run=0`, `session=0`; the C3 row retains the old
session and changes only the current market identity. These are the counters
that prove Git/capability drift and lifecycle progress do not silently free a
market slot.

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
