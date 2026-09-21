# A5 owner readout — FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1

## Entry

- Base/main: `5f658ad9a7a80a33db51dbd83b5e109e0deac1e8`
- A4 post-merge CI `35588267708`: success on that SHA
- PR #329 PATCH after independent review `SMIAL_A5_PR329_689d5d4c_REVIEW.md`
- No-write C1/C2 disposition:
  `docs/evidence/forge_evidence_identity_and_owner_gold/a1_no_write_c1_c2_disposition_v1.json`
  — per-session disposition; first-run without rewriting history;
  missing new-schema stamp does not zero a known look when freeze admission
  can be restored from earlier cycles

## Delivered (admission → lifecycle → occupancy → readback)

- Shared helper `hfic_evidence_identity.py`: market vs capability split,
  scientific slot + execution binding (actual representation payload),
  run identity, legacy disposition, stamp-only market budget with
  exact-bytes resume lookup bridge
- Lifecycle: market/capability stamps propagate through freeze → intermediate
  Critic → revise/runner-up → classify/complete; `list_hfic_sessions` and
  `load_session_bundle` restore immutable admission from earlier cycles
- Discovery: ladder reuse requires current-market applicability (F1a:
  ordinary PASS on C1+C2 does not answer C1+C2+C3 as `REUSED_VALID`)
- Consumers: A3 input receipt, preflight/slash identity + budget, ladder
  run identity + slot/binding, session freeze/persist/list/lookup
- Owner gold: G1–G12 plus F1a/F2 lifecycle counters; production bindings;
  incomplete market fail-closed

## Whole-path counters (production APIs)

| Phase | market stamp on listed session | budget occupancy |
|---|---|---|
| after freeze | present | ≥1 |
| after PASS_TO_CLASSIFICATION | present | ≥1 |
| after classification complete | present | ≥1 |
| after C3 import | prior session historical | new market starts fresh search |

## Non-claims

- No scientific market Forge / Prompt A–C / real Critic
- No A6, provider/VPS, historical rewrite, quota expansion
- Fixture gold ≠ alpha; continuous runtime reliability not proven
- Merge requires separate machine-rendered A5 owner phrase after readiness
