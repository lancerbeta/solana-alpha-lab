---
task_id: HFIC_CENSORING_DIAGNOSTIC_SCOPE_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-17'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: fa5855eb081bbb8ac87fa2e00e074686ce44f7ab
  expected_upstream: origin/main
  expected_upstream_oid: fa5855eb081bbb8ac87fa2e00e074686ce44f7ab
  expected_branch: cursor/hfic-censoring-diagnostic-scope-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Repair the canonical HFIC censoring diagnostic so denominator, census-state
  and duplicate gates apply to the frozen observation-mint population after
  full-file canonical bind, not the full discovery census, without changing
  frozen spec YAML/SHA, pins, science knobs or running the real diagnostic.

managed_write_set:
  - docs/tasks/HFIC_CENSORING_DIAGNOSTIC_SCOPE_REPAIR_V1.md
  - src/solana_alpha_lab/factory/hfic_censoring_ignorability_diagnostic.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - docs/reports/hfic_censoring_diagnostic_scope_repair/a1_owner_readout_v1.md
  - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_pinned_production_closure_v1.json
  - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - FROZEN_SPEC_MUTATION
  - CANONICAL_PIN_MUTATION
  - REAL_SCIENTIFIC_DIAGNOSTIC_RUN
  - HISTORICAL_RECEIPT_MUTATION
  - A1_DENOMINATOR_CLOSURE_REWRITE
  - PARQUET_OR_MANIFEST_REWRITE
  - LIVE_CORPUS_REPUBLISH
  - GENERIC_DENOMINATOR_FRAMEWORK
  - HARDCODED_PRODUCTION_FOUR_WAY
  - PROVIDER_CALL
  - Y_POINT_READ
  - FORGE_SESSION
  - REAL_MONEY_OR_DEPLOYMENT

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
      - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_censoring_diagnostic_scope_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CENSORING_DIAGNOSTIC_SCOPE_REPAIR_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=DESIGN_SPEC. Exact owner atom: diagnostic population projection
after canonical bind. Do not run the real scientific diagnostic. Do not
mutate frozen spec YAML/SHA, pins, parquet, manifests or LIVE CORPUS.

## Task Outcome Brief

- **Owner decision:** the canonical diagnostic currently counts
  `other`/`UNKNOWN_CENSUS_STATE` over the entire discovery census (138844).
  Apply four-way, unknown-state, empty-mint, duplicate-census, admitted
  coverage and comparable membership to census rows whose mint is in the
  frozen observation-mint set (610).
- **Product outcome:** receipt schema 1.1 names full-file and diagnostic
  population counts; `UNKNOWN_CENSUS_STATE` keys off `other_in_scope`;
  out-of-scope pre-X exclusions are not unknown.
- **Named consumer:** later READ-ONLY OPERATE scientific rerun of
  `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001`.
- **Cheapest falsifier:** synthetic tests A–H; pinned production closure
  JSON is read-only acceptance without permutations or data_plane IO.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase,
  guarded merge, post-merge readback.
- **Non-goals:** real diagnostic run; frozen spec/pin edits; parquet or
  LIVE CORPUS rewrite; historical receipt `2ce8af50…` mutation;
  `a1_denominator_closure_v1.json` rewrite; generic denominator framework;
  hardcoded 148/327/35/100 in the implementation.

## Decision packet

- **DECISION_DELTA:** keep full-file canonical bind; project diagnostic
  census as observation-mint intersection after bind. Receipt 1.1 keeps
  `counts["census_rows"]` as full-file total; `counts["other"]` aliases
  `other_in_scope`.
- **UNCERTAINTY_REMOVED:** whether 138234 capacity/hash/predicate rows
  outside the observation-mint set can still force `UNKNOWN_CENSUS_STATE`.
- **CAPABILITY_OR_EVIDENCE:** scoped diagnostic + tests A–H + pinned
  closure JSON.
- **STOP:** merge-readiness then granted phrase/guarded-merge; no OPERATE
  rerun in this atom.
- **NEXT:** separate READ-ONLY OPERATE scientific rerun.
- **REPLAN_TRIGGER:** any need to change frozen spec YAML/SHA, science
  knobs, pins, parquet, or to hardcode production four-way counts.

## Required semantics

1. Full-file canonical binding unchanged; population projection only after bind.
2. Diagnostic census = census rows whose mint is in distinct nonempty
   observation mints.
3. Receipt counts `census_rows_total`, `census_distinct_mints_total`,
   `discovered_in_observation_partition`, `diagnostic_population_census_rows`,
   `diagnostic_population_distinct_mints`, `out_of_scope_census_rows`.
   Pinned production expectation: 138844 / 138844 / 610 / 610 / 610 / 138234.
   Do not call 138234 unknown.
4. Four-way, `UNKNOWN_CENSUS_STATE`, empty mint after population construction,
   duplicate census/comparable, admitted coverage and comparable members on
   the diagnostic population. In-scope is capable of 148/327/35/100,
   `other_in_scope=0`, comparable=475 — do not hardcode those counts.
5. Fail-closed: observation mint absent from census;
   any census `X_ELIGIBLE` mint absent from observations; unexpected
   in-scope state remains `UNKNOWN_CENSUS_STATE`.
6. Duplicate-census scoped to diagnostic population; in-scope multi-row mint
   still inconclusive; out-of-scope excluded-mint duplicates must not kill
   148-vs-327 unless a separate file-level contract forbids them.
7. Do not mutate historical receipt `2ce8af50…`. Schema 1.1 additive.
   Never report 138234 as `other_in_scope`.
8. Do not edit `docs/evidence/hfic_censoring_ignorability_diagnostic/a1_denominator_closure_v1.json`.

## Tests A–H

- A: out-of-scope CAPACITY/HASH/PREDICATE do not trigger UNKNOWN.
- B: in-scope garbage still UNKNOWN.
- C: `X_ELIGIBLE` missing from observations still
  `CENSUS_MINT_MISSING_FROM_OBSERVATIONS`.
- D: observation mint missing from census fail-closed with
  `OBSERVATION_MINT_MISSING_FROM_CENSUS`, not collapsed into UNKNOWN.
- E: in-scope duplicate census inconclusive.
- F: out-of-scope duplicate must not invalidate the estimand.
- G: existing science tests still pass.
- H: pinned production closure as read-only acceptance without permutations.
  CI must not depend on machine-local `data_plane`.
