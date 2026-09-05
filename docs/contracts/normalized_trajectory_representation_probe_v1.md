---
schema: smial.normalized-trajectory-representation-probe
schema_version: '1.0'
preregistration_id: NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1
probe_id: NORMALIZED_TRAJECTORY_V1
probe_kind: REPRESENTATION_CHALLENGER
probe_state: PREREGISTERED_NOT_EXECUTED
auto_execute_after_cohort_import: false
implementation_status: CONTRACT_ONLY
hfic_prompt_family: HFIC-V1.2
max_packet_bytes: 16384
max_feature_families: 8
ninth_family_workaround: forbidden
corpus_dataset_id: DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001
evidence_role: EXPLORATORY_REUSE
confirmatory_reuse_forbidden: true
min_usable_yield_eligible: 10
min_usable_yield_eligible_owner: src/solana_alpha_lab/factory/early_market_panel_importer.py::MIN_USABLE_YIELD_ELIGIBLE
cohort_normalization: 'OFF'
cohort_normalization_activation: NEW_PREREGISTRATION_REQUIRED
current_live_cohort_scientific_content_accessed: false
control_run_required_first: true
one_registered_trial: true
scores_pnl: false
new_novelty_scorer: forbidden
projection_code_implemented: false
fields:
  PRICE:
    logical_id: PRICE
    field_id: FIELD-USD-PRICE-001
    family: PRICE_PATH
  LIQUIDITY:
    logical_id: LIQUIDITY
    field_id: FIELD-LIQUIDITY-USD-001
    family: LIQUIDITY_PATH
  VOLUME_PRIMARY:
    logical_id: VOLUME
    field_id: FIELD-STATS5M-TAKER-VOLUME-001
    family: ACTIVITY_VOLUME
    use_when: OBSERVED
    never_infer_from_buy_sell: true
    excluded_reason_if_invented: TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL
  VOLUME_FALLBACK_BUY:
    logical_id: VOLUME_BUY
    field_id: FIELD-STATS5M-BUY-VOLUME-001
    family: ACTIVITY_VOLUME
  VOLUME_FALLBACK_SELL:
    logical_id: VOLUME_SELL
    field_id: FIELD-STATS5M-SELL-VOLUME-001
    family: ACTIVITY_VOLUME
  TRADERS:
    logical_id: TRADERS
    field_id: FIELD-STATS5M-NUM-TRADERS-001
    family: TRADER_BREADTH
volume_channel_rule:
  if_taker_observed: VOLUME
  else_if_buy_and_sell_observed: ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL
  else: UNAVAILABLE
  emit_when_fallback: [VOLUME_BUY, VOLUME_SELL]
  never_label_fallback_as_taker: true
  never_sum_buy_plus_sell_into_one_series: true
forbidden_probe1_fields:
  - FIELD-HOLDER-COUNT-001
  - FIELD-MARKET-CAP-USD-001
  - FIELD-STATS5M-NUM-NET-BUYERS-001
  - FIELD-R0-TAKER-VOLUME-MIX-001
  - quotes
  - execution
  - missingness_motifs
  - holders
  - mcap
time:
  landmark_source: ObservationSchedule
  preserve_due_offset_seconds: true
  equal_spacing_fiction: forbidden
  interpolation: forbidden
  intra_interval_shape_reconstruction: forbidden
  pit_clock: first_reliable_available_at
  substitute_event_time_if_clock_missing: forbidden
  missing_clock_emits: M
normalization:
  own_history: log(value_t / value_first_observed)
  first_observed: first_admissible_prefix_point_with_strictly_positive_finite_observed_value
  future_points_in_denominator: forbidden
  invalid_or_nonpositive: M
  log_ratio_requires: strictly_positive_finite_observed_typed_values
motif:
  alphabet: [U, F, D, M]
  construction: adjacent_steps_on_ordered_landmarks
  U: adjacent_observed_value_strictly_greater
  D: adjacent_observed_value_strictly_less
  F: adjacent_observed_values_exactly_equal
  M: either_adjacent_value_not_legitimately_observed_or_log_ratio_invalid
  flat_threshold: EXACT_ZERO_CHANGE_ONLY
  epsilon_flat_band: forbidden
  outcome_tuned_threshold: forbidden
  reason_f_kept: exact equality needs no cohort snooping
pit:
  only_observations_with_first_reliable_available_at_le_T: true
  later_y_points_are_outcomes_not_x: true
  full_trajectory_for_earlier_decision: forbidden
  future_disappearance: forbidden
  future_cohort_rank: forbidden
  final_token_state_as_x: forbidden
  winner_conditioned_normalization: forbidden
  imputation: forbidden
  missing_stays_missing: true
trigger_all_required:
  - first_fresh_cohort_sealed_verified_imported
  - readiness_in_READY_VALID_or_READY_VALID_WITH_COVERAGE_LIMITATION
  - yield_eligible_ge_min_usable_yield_eligible
  - one_control_forge_run_on_unchanged_current_representation_same_evidence_epoch
  - control_terminal_is_no_worthy_or_banal_closed_duplicative_or_credible_representation_gap
  - not_case_c_observability
  - not_case_a_currently_grounded
case_a:
  probe_trigger: false
  next: CHEAPEST_MARKET_FALSIFIER
control:
  representation: unchanged_current_forge_packet
  same: [evidence_epoch, corpus, prior_work_memory, critic, search_budget, prompt_family, candidate_count_constraints]
challenger:
  representation: NORMALIZED_TRAJECTORY_V1_compact_prefix_motif
  packet_budget_owner: HFIC_MAX_PACKET_BYTES
  raw_trajectory_dump: forbidden
  variant_shopping: forbidden
novelty:
  wording_or_card_count_alone: not_material
  structural_signature_change_alone: not_sufficient
  required_distinct_axes: 2
  axes:
    - actor_counterparty
    - mechanism
    - population
    - decision_timestamp
    - state_transition
    - required_observable_relation
    - falsifier
    - primary_y
metrics_rank:
  - materially_new_grounded_mechanism_families
  - at_least_one_expressible_without_new_provider_or_data_capability
  - closed_duplicative_collision_rate
  - unresolved_requirement_rate
  - cheapest_decision_bearing_falsifier_concreteness
secondary_only:
  - structural_signature_diversity
  - candidate_count
pass_code: NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_PASS
kill_code: NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_KILL
invalid_codes:
  - INVALID_INSUFFICIENT_YIELD
  - INVALID_COVERAGE_BROKEN
  - INVALID_PACKET_BUDGET
  - INVALID_GROUNDING_BOUNDARY
  - INVALID_EVIDENCE_EPOCH_MISMATCH
  - INVALID_CONTROL_NOT_RUN
  - INVALID_TRIGGER_NOT_MET
  - INVALID_CASE_C_OBSERVABILITY
after_kill: RETURN_TO_PROJECT_CHAT_NO_AUTO_TRAJECTORY_ENGINE
after_pass_does_not_mean: alpha_exists
---

# NORMALIZED_TRAJECTORY_V1 preregistration

Authoritative freeze is the YAML front matter. This body restates it for agents. Do not
redesign after seeing first-cohort paths. This file is not permission to run the probe.

## What this is

A **representation challenger**, not production Forge architecture and not an alpha test.
Current Forge still shows corpus identity/fingerprints, coarse feature-family presence and
FEAT-* grounding. Sequences stay in sealed observations until a later execution atom
projects the compact motif defined here.

`PROBE_STATE=PREREGISTERED_NOT_EXECUTED`. Projection code, HFIC edits, `/hypothesis-forge`,
seal/import, provider calls and current-cohort scientific inspection are out of this atom.

Preserve `EXPLORATORY_REUSE` and `confirmatory_reuse_forbidden=true`.

## When the probe may run

Not automatically after import. All trigger conjuncts in the front matter must be true,
including one CONTROL `/hypothesis-forge` on the **unchanged current representation** for
that exact evidence epoch.

If CONTROL already yields a credible `CURRENTLY_GROUNDED` mechanism (CASE A):
`PROBE_TRIGGER=FALSE`, `NEXT=CHEAPEST_MARKET_FALSIFIER`.

CASE C (observability failure) is `INVALID_CASE_C_OBSERVABILITY`, not KILL.

## Fields and volume channel

Probe 1 uses only PRICE, LIQUIDITY, trading-activity volume, and TRADERS. Canonical FIELD
IDs are frozen in the front matter.

Taker volume is used only when truly `OBSERVED`. Do not invent it from buy+sell
(`TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL`). If taker is unavailable and both buy and sell
are `OBSERVED`, emit two motifs `VOLUME_BUY` and `VOLUME_SELL` under
`ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL`. Do not sum them into one fake taker series.

Holders, mcap, net buyers, missingness motifs, quotes and execution are not Probe 1.

## Time, PIT, normalization, motif

Use ObservationSchedule landmarks with `first_reliable_available_at <= T`. Preserve
`due_offset_seconds`. No equal-spacing fiction, interpolation, or intra-interval shape.

If the PIT clock is missing, emit `M`. Do not substitute event/request time.

Own-history normalization is `log(value_t / value_first_observed)` only for strictly
positive finite observed values. No future point in the denominator.
`COHORT_NORMALIZATION=OFF`.

Motif alphabet is `U|F|D|M` on **adjacent** landmark steps. `F` is exact zero change only.
No epsilon and no outcome-tuned flat band.

Compact packet form (schema, not data):

```text
PRICE: U-U-F-D
LIQUIDITY: U-F-F-D
VOLUME: U-U-D-D
TRADERS: U-F-D-D
```

Do not dump raw trajectories. HFIC `MAX_PACKET_BYTES=16384` remains authoritative. If the
challenger cannot fit after existing truncation, stop as `INVALID_PACKET_BUDGET`. Do not
add a ninth feature family.

Later Y points are outcomes, not X for an earlier T. Missing stays missing. No imputation.

## Comparison, novelty, PASS / KILL / INVALID

CONTROL = current representation. CHALLENGER = same evidence epoch, corpus, prior-work,
Critic, search budget, prompt family and candidate-count constraints, with only this
compact motif added/replaced inside the packet budget. One registered version. No variant
shopping. Never score PnL.

Material novelty requires difference from CONTROL **and** closed/duplicative families on
≥2 frozen Forge axes. A changed `structural_signature_v1_sha256` is not enough if the
semantic delta is trivial. Reuse existing HFIC machinery; do not add a novelty scorer.

`NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_PASS` only if at least one challenger candidate
is unavailable to CONTROL, differs on ≥2 axes from closed families, is grounded in current
PIT evidence without a new provider/data-platform capability, survives independent Critic
without duplicate/reformulation kill, and has a concrete cheap falsifier. PASS means the
search space expanded. It does not mean alpha exists.

`NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_KILL` if zero such mechanisms, only wording or
signature variants, only closed-family restatements, the useful effect needs intra-interval
data not collected, unresolved requirements mainly increase, a second unregistered variant
is required, or the result is explained by budget/evidence/model mismatch.

INVALID is not KILL. Use the front-matter `invalid_codes`. After KILL, return to Project
Chat; do not automatically build a more sophisticated trajectory engine.

CASE E: if lifecycle candidates fail solely because FIELD-* cannot legally ground through
the current FEAT-* contract, stop as `INVALID_GROUNDING_BOUNDARY`. Do not silently widen
feature grounding inside the experiment.

## Non-goals

No trajectory projection implementation, HFIC modification, new feature family, generator,
ranker, embeddings, vector/graph DB, clustering, k-Shape, PELT, GP lead-lag, neural
sequence representation, autonomous search, provider/data changes, current-cohort
inspection, or experiment execution.
