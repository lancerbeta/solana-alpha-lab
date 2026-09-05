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
  preferred_schedule_id: OBS-ALWAYS-ON-TOKENS-V2-LIFECYCLE-21D-001
  imported_schedule_identity: use_exact_schedule_bound_to_imported_corpus
  schedule_shape: one_x_point_plus_declared_y_points
  x_selection_menu_seconds: [300, 600, 900]
  x_selection_menu_is_not_collected_prefix: true
  preferred_x_due_offset_seconds: 300
  declared_y_due_offset_seconds: [900, 1800, 3600, 7200, 14400, 43200, 86400]
  decision_t_point_id: Y1800
  decision_t_due_offset_seconds: 1800
  decision_t_is_not_forge_wall_clock: true
  delay_after_ready_to_lengthen_motif: forbidden
  prefix_slots: all_schedule_points_with_due_offset_le_1800
  missing_or_late_clock_keeps_slot_emits: M
  drop_slot_when_clock_missing: forbidden
  y_points_after_decision_due_are_outcomes_not_x: true
  min_motif_steps: 2
  min_prefix_slots: 3
  schematic_motif_example_length: not_a_requirement
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
  - control_terminal_permits_probe
  - not_case_c_observability
  - not_case_a
control_terminals_permit_probe:
  - NO_WORTHY_HYPOTHESIS
  - KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED
case_a:
  probe_trigger: false
  next: CHEAPEST_MARKET_FALSIFIER
  if_control_critic_terminal_in:
    - PASS_FAST_LANE_READY
    - PASS_CHANGE_LANE_REQUIRED
case_c:
  code: INVALID_CASE_C_OBSERVABILITY
  if_any:
    - control_forge_context_or_preflight_cannot_be_built
    - control_critic_terminal_in_KILL_UNBOUND_EVIDENCE_or_KILL_DATA_INFEASIBLE
    - imported_corpus_absent_from_current_forge_packet
invalid_coverage_broken_if:
  - discovery_coverage_class_is_GAP_CONFIRMED
  - readiness_not_in_READY_VALID_or_READY_VALID_WITH_COVERAGE_LIMITATION
unknown_or_suspected_coverage_may_use: READY_VALID_WITH_COVERAGE_LIMITATION
control:
  representation: unchanged_current_forge_packet
  same: [evidence_epoch, corpus, prior_work_memory, critic, search_budget, prompt_family, candidate_count_constraints]
control_terminal_else: INVALID_TRIGGER_NOT_MET
challenger:
  representation: NORMALIZED_TRAJECTORY_V1_compact_prefix_motif
  packet_surgery: REPLACE_WITHIN_EXISTING_TRUNCATION
  packet_budget_owner: HFIC_MAX_PACKET_BYTES
  raw_trajectory_dump: forbidden
  variant_shopping: forbidden
  add_versus_replace_shopping: forbidden
case_e:
  code: INVALID_GROUNDING_BOUNDARY
  if: lifecycle_field_sequences_cannot_legally_ground_through_current_feat_contract
  silently_widen_feature_grounding: forbidden
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
pass_requires_all:
  - at_least_one_challenger_candidate_unavailable_to_control
  - differs_from_closed_or_duplicate_families_on_ge_2_frozen_axes
  - grounded_in_current_pit_evidence_without_new_provider_or_data_platform
  - survives_independent_critic_without_duplicate_or_reformulation_kill
  - has_concrete_cheap_falsifier
pass_means: trajectory_representation_expanded_useful_hypothesis_search_space_this_epoch
kill_code: NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_KILL
kill_if_any:
  - zero_materially_new_grounded_mechanisms
  - only_wording_or_signature_variants
  - only_restatements_of_closed_families
  - useful_effect_requires_intra_interval_data_not_collected
  - challenger_mainly_increases_unresolved_requirements
  - useful_effect_depends_on_second_unregistered_representation_variant
  - result_explained_by_different_budget_evidence_or_model
invalid_codes:
  - INVALID_INSUFFICIENT_YIELD
  - INVALID_INSUFFICIENT_PREFIX
  - INVALID_COVERAGE_BROKEN
  - INVALID_PACKET_BUDGET
  - INVALID_GROUNDING_BOUNDARY
  - INVALID_EVIDENCE_EPOCH_MISMATCH
  - INVALID_CONTROL_NOT_RUN
  - INVALID_TRIGGER_NOT_MET
  - INVALID_CASE_C_OBSERVABILITY
invalid_insufficient_prefix_if:
  - motif_steps_lt_min_motif_steps
  - prefix_slots_lt_min_prefix_slots
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

If CONTROL `critic_terminal` is `PASS_FAST_LANE_READY` or `PASS_CHANGE_LANE_REQUIRED` (CASE A):
`PROBE_TRIGGER=FALSE`, `NEXT=CHEAPEST_MARKET_FALSIFIER`.

CONTROL permits the probe only when `critic_terminal` is `NO_WORTHY_HYPOTHESIS` or
`KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED`. Do not invent a post-hoc "representation gap"
terminal after seeing candidates.

CASE C is `INVALID_CASE_C_OBSERVABILITY` when CONTROL cannot build FORGE_CONTEXT / preflight
fails, the imported corpus is absent from the current packet, or CONTROL ends
`KILL_UNBOUND_EVIDENCE` / `KILL_DATA_INFEASIBLE`. That is not KILL.

`INVALID_COVERAGE_BROKEN` only if `discovery_coverage_class=GAP_CONFIRMED` or readiness is
outside the two allowed READY states. `DISCOVERY_COVERAGE_UNKNOWN` / `GAP_SUSPECTED` may
remain `READY_VALID_WITH_COVERAGE_LIMITATION` as already allowed by live-cohort seal.

## Fields and volume channel

Probe 1 uses only PRICE, LIQUIDITY, trading-activity volume, and TRADERS. Canonical FIELD
IDs are frozen in the front matter.

Taker volume is used only when truly `OBSERVED`. Do not invent it from buy+sell
(`TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL`). If taker is unavailable and both buy and sell
are `OBSERVED`, emit two motifs `VOLUME_BUY` and `VOLUME_SELL` under
`ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL`. Do not sum them into one fake taker series.

Holders, mcap, net buyers, missingness motifs, quotes and execution are not Probe 1.

## Time, PIT, normalization, motif

Bind landmarks to the imported corpus ObservationSchedule. Preferred campaign identity is
`OBS-ALWAYS-ON-TOKENS-V2-LIFECYCLE-21D-001`. Git shape is **one** `x_point` chosen from
the menu {300, 600, 900} (preferred 300) plus Y due offsets 900, 1800, 3600, 7200, 14400,
43200, 86400. That menu is not three collected X landmarks. Offset 600 is not a default Y.

Probe 1 decision `T` is the **Y1800** due (1800 seconds), not Forge wall-clock and not a
later Y. Do not wait after READY to lengthen motifs. Prefix **slots** are every schedule
point with `due_offset_seconds <= 1800` (default: X300, Y900, Y1800). Points after 1800
remain outcomes, not X. A missing/late PIT clock keeps the slot and emits `M`; do not drop
the slot.

Need ≥3 prefix slots and ≥2 adjacent motif steps. Otherwise `INVALID_INSUFFICIENT_PREFIX`.
The compact `PRICE: U-U-F-D` sketch is schema-only; it does not freeze motif length.

Preserve `due_offset_seconds`. No equal-spacing fiction, interpolation, or intra-interval
shape. If the PIT clock is missing, emit `M`. Do not substitute event/request time.

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

`NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_PASS` only if every `pass_requires_all` conjunct
in the front matter holds. PASS means the search space expanded. It does not mean alpha
exists (`after_pass_does_not_mean: alpha_exists`).

`NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_KILL` if any `kill_if_any` conjunct holds.

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
