---
task_id: HFIC_FORGE_VISION_INTEGRITY_CLOSURE_V1
task_version: '1.0'
status: VALIDATED
as_of: '2026-09-16'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 22c8b1ae115cf82f6a4793d30a1b6ceb41032182
  expected_upstream: origin/main
  expected_upstream_oid: 22c8b1ae115cf82f6a4793d30a1b6ceb41032182
  expected_branch: cursor/hfic-forge-vision-integrity-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Close the Forge vision-integrity problem durably: positive suppression
  authority for family hard-closes, deterministic machine vision-integrity
  receipts for bounded Forge packets with a NO_WORTHY trust gate, PR308
  reopened-prior invariants preserved, and a mechanically runtime-ready
  NORMALIZED_TRAJECTORY_V1 seam for the real imported cohort — without
  unbounded context, packet-limit increases, or new infrastructure.
managed_write_set:
  - docs/tasks/HFIC_FORGE_VISION_INTEGRITY_CLOSURE_V1.md
  - scripts/hypothesis_forge.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_released_trajectory_projection.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/hfic_representation_probe.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_suppression_semantics.py
  - src/solana_alpha_lab/factory/hfic_vision_integrity.py
  - tests/test_hfic_fresh_control_decision_integrity_closure_v1.py
  - tests/test_hfic_legacy_science_rebase.py
  - tests/test_hfic_manual_grounding_contract_diagnostics_v1.py
  - tests/test_hfic_packet14_availability_fast_lane_guard_v1.py
  - tests/test_hfic_released_trajectory_projection_v1.py
  - tests/test_hfic_reopened_prior_search_routing_v1.py
  - tests/test_hfic_representation_probe.py
  - tests/test_hfic_session.py
  - tests/test_hfic_suppression_positive_authority_v1.py
  - tests/test_hfic_vision_acceptance_operations_v1.py
  - tests/test_hfic_vision_integrity_v1.py
  - docs/evidence/hfic_forge_vision_integrity_closure/a1_real_c1_vision_acceptance_v1.json
  - docs/reports/hfic_forge_vision_integrity_closure/a1_owner_readout_v1.md
  - catalog/assets/core.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - SCIENTIFIC_ESTIMAND_AMBIGUITY
  - NEW_PORTABILITY_JUDGMENT_REQUIRED
  - FROZEN_CHALLENGER_SEMANTICS_CHANGE_REQUIRED
  - NEW_PROVIDER_DATA_REQUIRED
  - SERVICE_OR_DB_REQUIREMENT
  - PACKET_INTEGRITY_VIA_SEARCH_STRATEGY_CHANGE
  - REAL_C1_SCIENTIFIC_VALUES_INSPECTION_REQUIRED
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_forge_vision_integrity_closure/a1_real_c1_vision_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FORGE_VISION_INTEGRITY_CLOSURE_V1

## Mission

Close the Forge "vision integrity" problem durably: positive suppression
authority, machine vision integrity for bounded packets, PR308 prior-body
invariants, and a mechanically runtime-ready NORMALIZED_TRAJECTORY_V1 seam —
without unbounded context, packet-limit increases, or new infrastructure.

## Root causes (proven, read-only review 2026-09-15)

1. **Suppression authority inflation** — `classify_source_payload` treats any
   `*_FAMILY` terminal (or `family_close`/scientific-terminal naming) as
   `SCIENTIFIC_CLOSE_VALID` + `reopen_forbidden=true` without requiring
   positive machine evidence of scientific result / scope / portability.
   Observed false positive: `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`
   (`design_probe.science=false`, quote-only screening exhausted).
2. **Bounded packet silently blind** — `build_forge_context_packet` drops
   semantic routes and all `feature_grounding_entries` under the 16384-byte
   cap with only a truncation receipt; `FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO`
   (`PIT_READY`) availability semantics can vanish from Prompt A without any
   typed STOP, and NO_WORTHY remains persistable afterwards.
3. **Challenger runtime seam** — `NORMALIZED_TRAJECTORY_V1` projector accepts
   imported corpus bindings, but `hfic_representation_probe` hard-fails any
   non-synthetic `corpus_binding` (`_assert_representation_bound_to_readiness`
   requires `DEFAULT_SCHEDULE.corpus_binding`), so a real imported release
   cannot produce a verified projection/input receipt without another Git atom.

## Named consumer

HFIC Prompt A (candidate generation), HFIC preflight, representation probe
runtime, and the owner operating the post-merge C1 commissioning path.

## Outcome (DoD)

1. `*_FAMILY` naming alone can never produce `reopen_forbidden=true`; family
   hard-close requires positive typed authority (scientific result + scope
   identity + population/estimand compatibility + hash-bound source; no
   `science=false`-style negation; RDP typed runtime receipts remain
   authoritative).
2. Non-portable/ambiguous items persist as typed prior/history
   (`reopen_forbidden=false`), never as family hard-close. Historical receipts
   are not rewritten.
3. Every `build_forge_context_packet` result carries a deterministic
   `vision_integrity` receipt: every omitted feature/grounding/semantic/
   capability item classified `REDUNDANT_WITH_RETAINED_INFORMATION` or
   `INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION`; material/unknown omission ⇒
   `FORGE_VISION_INTEGRITY_BLOCKED` typed STOP. `NO_WORTHY_HYPOTHESIS` and the
   selected-candidate path cannot start/persist with vision integrity ≠ PASS
   for their declared surface.
4. Packet stays ≤ 16384 bytes via compaction (family-level availability
   index), never via silent material loss.
5. PR308 invariants survive: H11/H13 bodies/ranking 1:1, dropped_priors=0,
   defective session immutable, quarantine append-only.
6. Non-synthetic verified release → verified projection/input receipt →
   existing challenger adapter, with provenance binding
   (release/source/census/observations/schedule/activation), PIT cutoffs
   frozen, missingness=M, no mint identity; terminal
   `NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED`. No scientific
   execution in this atom.
7. Real C1 read-only acceptance over `local/factory_v1/data_plane` reaches
   `FORGE_VISION_ACCEPTANCE_PASS` without materializing trajectory motifs.

## Non-goals

No CONTROL run, no challenger execution, no Critic, no provider calls, no C2
import, no deploy, no ranker change, no search-budget change, no
representation-semantics change, no packet-limit increase, no new service/DB,
no historical receipt rewrite, no per-cohort suppressor maintenance.

## Review roles (required_review_roles)

CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC
(owner-operable CLI changes: new read-only acceptance subcommand).

## Stop conditions

Per owner contract: scientific estimand ambiguity, new scientific judgment for
portability beyond canonical evidence, frozen challenger semantics change,
new provider data, service/DB requirement, packet integrity only via search
strategy change, or need to inspect real C1 scientific values.

## Rollback

Revert the merge commit; no data-plane mutation exists by design (read-only
acceptance; apply path is separately owner-authorized post-merge).
