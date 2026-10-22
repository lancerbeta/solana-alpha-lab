---
task_id: FORGE_BLOCK_COMPARATOR_READOUT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: bd4f9fd5a73fa4de48c74b3c9eca7ff7acf5858f
  expected_upstream: origin/main
  expected_upstream_oid: bd4f9fd5a73fa4de48c74b3c9eca7ff7acf5858f
  expected_branch: claude/forge-block-comparator-readout-v1
  dirty_mode: ALLOW_REPORTED
objective: A future native episode MAIN saves matched and its own comparator inside every calendar block and cohort, and the pair reaches saved detail, the bounded readout and the fragment source snapshot, without touching any saved result.
managed_write_set:
- docs/tasks/FORGE_BLOCK_COMPARATOR_READOUT_V1.md
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_discovery_detail.py
- src/solana_alpha_lab/factory/research_fragments.py
- tests/test_hfic_block_comparator_readout_v1.py
- tests/test_hfic_list_scope_executor_v1.py
- tests/test_hfic_list_aware_vertical_v1.py
- docs/contracts/forge_downside_descriptive_v1.md
- docs/operator/RESEARCH_FRAGMENTS_V1.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- docs/evidence/forge_block_comparator_readout_v1/**
- docs/evidence/list_a_confirmation_protocol_freeze_v1/main-refresh.json
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_NEW_REAL_MARKET_LOOK_IN_THIS_ATOM
- NO_CANONICAL_RESEARCHSTORE_WRITE_IN_THIS_PR
- STOP_IF_COMPATIBILITY_NEEDS_A_HISTORY_MIGRATION_OR_A_CORRECTION_FRAMEWORK
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/forge_downside_descriptive_v1.md
    - docs/operator/RESEARCH_FRAGMENTS_V1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_block_comparator_readout_v1/completion.json
    - docs/evidence/forge_block_comparator_readout_v1/independent-review.json
    - docs/evidence/forge_block_comparator_readout_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# Block-local comparator readout (FORGE_BLOCK_COMPARATOR_READOUT_V1)

Owner request 2026-10-22, after the bounded ENTRY_SHAPE run. ENTRY_SHAPE A and B
are accepted as finished: two saved exact-question negatives, MAIN 2 of 2,
PAUSED_CAP, no unresolved reservation, universe gate free. Nothing in this atom
re-reads, revises or re-assesses them.

DECISION_DELTA: the next episode MAIN answers "how does matched look against its
own comparator on the same day and in the same cohort", not only against the pool.
UNCERTAINTY_REMOVED: a weak shape versus a bad market day can be told apart from
the saved result. CAPABILITY_OR_EVIDENCE: an additive native output and a
hand-computed two-day oracle through the real compute, coherence, readout, fragment
and saved-detail owners; real A/B and both RFV are only read back cold.
STOP: exact-head CI, merge readiness, owner phrase. NEXT: the first separately
authorised scientific MAIN may read the pairs.
REPLAN_TRIGGER: compatibility needs a history migration or a correction framework.

## Why the full JSON is not enough

`_cohort_rows` and the calendar rows aggregate only the matched sample;
`baseline` is one pooled number that includes matched. The per-block baseline
returns are never saved, so a pooled comparison cannot be decomposed afterwards.
The compact readout also cuts each list to four rows.

## Semantics

Additive `block_comparator` in a fresh episode result (new calculation version
`HFIC_TEMPORAL_DISCOVERY_CALC_EPISODES_V4`), built from the members and cohort seats
the one existing computation already holds:

- per UTC decision day and per cohort: `matched` and `reference` sides with
  eligible/observed/missing N, mean, median and each side's own downside;
- reference = native comparator: every decision-eligible member (matched and
  feature-UNKNOWN included) for `SAME_DECISION_ELIGIBLE`; exactly the
  decision-eligible non-matched members for `MATCHED_VS_ELIGIBLE_COMPLEMENT`;
- delta only when both sides observed and, for an inclusive reference, something
  beyond matched was observed (`NO_UNMATCHED_OBSERVED` otherwise); empty sides are
  typed, never zero; inclusive deltas are not comparable across blocks of different
  matched share (full state list and statuses: the contract below);
- no averaging or subtraction of quantiles/ES10; no new metric, threshold, query
  field, scheduler, API or statistics stack;
- coherence validator extended: pairs must equal the saved rows and add up to
  the native baseline or complement; a V4 result must carry the block.

Contract and operator text: `docs/contracts/forge_downside_descriptive_v1.md`
(section "Block-local comparator"), `docs/operator/RESEARCH_FRAGMENTS_V1.md`.

## Compatibility

V3 and earlier stay current and readable; same-query retry returns the saved
result; nothing is recomputed, revised or re-hashed. Older results are marked
`NOT_SAVED_BY_THIS_CALCULATION_VERSION` (other statuses: contract) only by a runtime hint in `discovery-show`.
`descriptive_return_readout` and the fragment summary add the block only when the
result saved it, so older capsules, frozen working views and archive fingerprints
are byte-identical. BASE_X is unchanged. Rollback after a V4 result exists is
forward-fix only (keep a V4 reader, delete no history).

## Out of scope

New real market looks, recomputing A/B, new assessments, admin UI, new providers,
libraries, thresholds, horizons, cost model, correction/versioning framework.
