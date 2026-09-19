# HFIC_FORGE_CONTROL_READY_NEGATIVE_PRIOR_REPAIR_V1 — Owner readout

Date: 2026-09-19 · Route: DIRECT_CURSOR_DELIVERY

Predecessor: `HFIC_C2_FORGE_READY_MEMORY_SEMANTICS_AUDIT_V1` (`CONTRACT_BUG_PROVEN`).

## What changed

`forge_control_ready` keeps session-id quarantine integrity (`session_id not in blocked`).
It no longer denies eligible `HARD_CLOSE` / `PARK` capsules as `QUARANTINED_MEMORY_ELIGIBLE`.

## What did not change

- Memory-policy identity: `policy_sequence=2`, `memory_eligibility_sha256=be64c8a3…173e`
- `HFIC-SESS-60FB3DA7C8EB33FC` not quarantined
- C2 evidence epoch `6cf78400…16caf`
- CONTROL packet bound `16384`
- CONTROL-first routing (`control_run_required_first=true`)

## Real C2 read-only acceptance

`forge-control-ready --imported-cohort-id REL-20260909T111900Z-20260916T111900Z`

- terminal: `FORGE_CONTROL_READY`
- `dataset_manifest_id`: `dataset-f5245e924d08f16fe02e3ee416183923f7ef2ef2426b7db2db90e8705dd1680a`
- `evidence_epoch_sha256`: `6cf784007d3c8728459633bd7ceb83f95d21adbaaabf7945e6be498f47a16caf`
- `control_search_action`: `START_NEW_SESSION`
- `live_corpus_in_packet`: true
- no ResearchStore / session writes

## Residual (next atom, not this repair)

CONTROL packet still typed-STOP `MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND` (bound 16384; fail-point bytes above bound). Do not quarantine 60FB or drop HARD_CLOSE to paper over capacity.

## SCIENCE_CRITIC answers

- Does patch change any historical scientific disposition? **NO.**
- Does patch make HARD_CLOSE/PARK scientifically eligible when policy had quarantined their session? **NO.**
- Does patch merely stop misclassifying legitimate eligible negative prior? **YES.**

## ARCHITECTURE_CRITIC answers

- Second memory-policy authority? **NO.**
- Evidence epoch / search budget altered? **NO.**
- Capacity remains a separate fail-closed gate? **YES.**
