# FORGE_TEMPORAL_OPERABILITY_REPAIR_V1 owner readout

Finish atom: predicate vs matched-outcome input fitness + disposition-bound close.
Base main: `86b24cb1abe5867becc1ead16efb3754044550df`. Prior verified tip: `12ce9bce`.

## Closed this increment

- **INPUT FITNESS:** Required predicate-path cells (X300 / decision / features) and matched-scope outcomes (reference / exit) are assessed separately. Feature lineage with `feature_unknown` on every eligible member stamps `technical_stop` and blocks `READY_TO_FREEZE`. Population/decision lineage stops are not cancelled by companion scientific membership (e.g. `PIT_LIQUIDITY_MISSING`). Unmatched exit/reference lineage no longer converts a valid false-predicate zero-match into `TECHNICAL_STOP`. `NOT_X_ELIGIBLE` still does not cancel an eligible-scope stop; pooled/by_cohort N and reasons stay aligned.
- **COMPLETION BINDING:** `close_repair_continuation` requires a completed cycle stamped with this disposition and a session receipt new vs the bound parent. Apply → immediate close on parent `NO_WORTHY` refuses with `REPAIR_EXECUTION_NOT_COMPLETE`, records delta=0, `AUTHORIZED` retained. Parent DONE, foreign marker, and pending states refuse without write.
- Prior P1-A/P1-B and G11 remain closed (census scope, canonical terminal, OBSERVABILITY bypass only for repair-marked completions; ordinary completed + admission STOP is a non-writing blocked overlay — never persists over the durable terminal).

## Outcome matrix (test-falsified; tip PROVEN deferred to exact-head CI + reviews)

| Boundary | Status | Evidence |
|---|---|---|
| X300 / decision / feature lineage → technical stop | FALSIFIED | `test_x300_*`, `test_decision_lineage_*`, `test_feature_lineage_*` |
| Reference lineage via decision cell → predicate fitness stop | FALSIFIED | `test_reference_lineage_absence_blocks_via_predicate_fitness` |
| Exit lineage on matched scope → technical stop | FALSIFIED | `test_exit_lineage_on_matched_scope_is_technical_stop` |
| False predicate + unmatched exit lineage stays scientific | FALSIFIED | `test_false_predicate_with_unmatched_exit_lineage_stays_scientific` |
| NOT_X_ELIGIBLE does not cancel eligible feature stop | FALSIFIED | `test_feature_lineage_absence_preserves_reason` (mixed census) |
| Valid zero-match remains scientific | FALSIFIED | `test_valid_zero_match_*` |
| Apply → immediate close refuses parent absorption | FALSIFIED | `test_apply_immediate_close_refuses_parent_done_absorption` |
| Incomplete / pending close refused | FALSIFIED | `test_repair_completion_refuses_*` |
| Bound execution → NO_WORTHY / selected / runner-up → close → readback | FALSIFIED | Vertical B + MetadataStop + OwnerContinuationRunnerUpPass |
| Ordinary completed + OBSERVABILITY_BLOCKED is non-writing overlay | FALSIFIED | `test_ordinary_completed_observability_block_is_non_writing_readback` |
| Primary KILL → runner-up PASS keeps OWNER_CANDIDATE + survivor | FALSIFIED | `OwnerContinuationRunnerUpPassTests` |
| Crash recovery between terminal/receipt/CLOSED | FALSIFIED | MetadataStop post-close replay path |

## Owner production scenarios

- **Data:** journal path with technical stop + NOT_X_ELIGIBLE census; scientific positive vs zero-match distinct (`OwnerDataScenarioTechnicalAndScientificTests`). Vertical A published parity after tip commit/hash rebind.
- **Continuation:** authorized disposition → new bound execution → close; apply-without-execution cannot close; runner-up PASS keeps `OWNER_CANDIDATE` with survivor = runner-up id.

## Still closed from prior increments

Mixed clocks; journal/DocumentRunner parity; selected repair lifecycle; post-close preference of repair-marked receipt; metadata technical stop vs SEARCH_EXHAUSTED; opaque looks do not credit scientific search.

## Metadata-only live cohort note

Live S3 metadata read not re-run in this atom. Disposition remains UNKNOWN for occurrence/request readiness until a separate metadata-only read. Historical live parent for future apply (re-check runtime before use):

- run `FORGE-RUN-1CEB81C6C91AC1A8`
- session `HFIC-SESS-222A589D8A2731D8`
- focus `COHORT_STRATIFIED_LIFECYCLE_PATHS`

## Unexecuted post-merge plan

1. No-write readiness/plan for the exact live parent.
2. Separate owner permission for live apply.
3. One ordinary continuation in the remaining budget; current terminal/replay.
4. If metadata blocker: fix input constraint first — no scientific close, no arbitrary rerun.

## Non-claims

NO_LIVE_APPLY, NO_MARKET_FORGE, NO_MERGE, NO_ALPHA.
