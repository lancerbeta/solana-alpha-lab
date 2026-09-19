# HFIC_FORGE_CONTROL_READY_NEGATIVE_PRIOR_REPAIR_V1 — Owner readout

Date: 2026-09-19 · Route: DIRECT_CURSOR_DELIVERY

Predecessor: `HFIC_C2_FORGE_READY_MEMORY_SEMANTICS_AUDIT_V1` (`CONTRACT_BUG_PROVEN`).

## What changed

`forge_control_ready` keeps session-id quarantine integrity (`session_id not in blocked`).
It no longer denies eligible `HARD_CLOSE` / `PARK` capsules as `QUARANTINED_MEMORY_ELIGIBLE`.

## What did not change

- Memory-policy identity: `policy_sequence=2`, `memory_eligibility_sha256=be64c8a3c5fd683dbb1aae896e498b905a7318c327a48fc4552b9c9e7f69173e`
- `HFIC-SESS-60FB3DA7C8EB33FC` not quarantined (quarantined sessions remain 14)
- C2 LIVE CORPUS `dataset-f5245e924d08f16fe02e3ee416183923f7ef2ef2426b7db2db90e8705dd1680a`
- CONTROL packet bound `16384`
- CONTROL-first routing (`control_run_required_first=true`)
- No HYPOTHESIS_VERSION / DECISION_EVENT / memory-policy / session writes

## Real C2 read-only acceptance

`forge-control-ready --imported-cohort-id REL-20260909T111900Z-20260916T111900Z`

- terminal: `FORGE_CONTROL_READY`
- `dataset_manifest_id`: `dataset-f5245e924d08f16fe02e3ee416183923f7ef2ef2426b7db2db90e8705dd1680a`
- `control_search_action`: `START_NEW_SESSION`
- `live_corpus_in_packet`: true
- ResearchStore inventory unchanged on the capacity diagnostic

`evidence_epoch_sha256` is now `dadb0fed59e50c581640d8e493b80915dc5576b39093e5ffb9ead87399b8c9f9`.
That hex moved because `catalog/catalog_manifest.yaml` is inside `_EPOCH_FILES` and this atom registered two Catalog assets (`assets: 1811`). C2 corpus bytes and memory-policy identity did not change. Predecessor hex `6cf78400…16caf` was the pre-catalog-bind value on `origin/main`.

## Residual (next atom, not this repair)

CONTROL packet still typed-STOP `MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND`.
Bound 16384. First encode 18166 bytes; fail-point after semantic drop 17242 bytes.
Do not quarantine 60FB or drop HARD_CLOSE to paper over capacity.

## Reviews

Isolated: CODE_REVIEWER PASS, GOAL_DOD_CRITIC PASS, ARCHITECTURE_CRITIC PASS
(`packet_fingerprint_sha256=9cc150f4049c746a232da092cd6759656be6b68341ec59c74cf074b85608faca`).
SCIENCE_CRITIC (extra, not in `required_review_roles` enum): PASS.

## SCIENCE_CRITIC answers

- Does patch change any historical scientific disposition? **NO.**
- Does patch make HARD_CLOSE/PARK scientifically eligible when policy had quarantined their session? **NO.**
- Does patch merely stop misclassifying legitimate eligible negative prior? **YES.**

## ARCHITECTURE_CRITIC answers

- Second memory-policy authority? **NO.**
- Evidence epoch / search budget altered? **NO.**
- Capacity remains a separate fail-closed gate? **YES.**

`CAPABILITY_RADAR_NOW=NONE`. STOP before owner merge phrase.
