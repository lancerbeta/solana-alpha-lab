---
task_id: HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC_V1
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

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 461f5c1be2fb3f88f23aaac9eb7bf522fa1d11c0
  expected_upstream: origin/main
  expected_upstream_oid: 461f5c1be2fb3f88f23aaac9eb7bf522fa1d11c0
  expected_branch: cursor/hfic-censoring-ignorability-diagnostic-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Register and implement a reusable offline, PIT-compatible, seeded-deterministic
  diagnostic that tests whether census censored_late membership shows detectable
  selection on a frozen pre-decision X300 surface. The capability must not certify
  MAR, ignorability, identification, alpha, or market-hypothesis validity, must
  never read Y-point values, and must not run against canonical active RDP in
  this delivery atom.

managed_write_set:
  - docs/tasks/HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC_V1.md
  - configs/hfic_censoring_ignorability_diagnostic_v1.yaml
  - configs/experiment_capability_registry_v2.yaml
  - src/solana_alpha_lab/factory/hfic_censoring_ignorability_diagnostic.py
  - src/solana_alpha_lab/factory/capabilities.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - tests/test_discovery_evidence_release_bridge.py
  - scripts/hypothesis_forge.py
  - catalog/catalog_manifest.yaml
  - docs/reports/hfic_censoring_ignorability_diagnostic/a1_owner_readout_v1.md
  - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_denominator_closure_v1.json
  - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_frozen_spec_v1.json
  - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - CANONICAL_ACTIVE_RDP_SCIENTIFIC_RUN
  - Y_POINT_READ
  - PROVIDER_CALL
  - PACKET_BUDGET_CHANGE
  - RANKER_OR_SEARCH_BUDGET_CHANGE
  - QUARANTINE_OR_MEMORY_POLICY_CHANGE
  - CRITIC_OR_REPRESENTATION_CHANGE
  - MARKET_HYPOTHESIS_EXPERIMENT
  - MAR_OR_IDENTIFIABILITY_CERTIFICATION
  - REAL_MONEY_OR_PROMOTION

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
      - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_censoring_ignorability_diagnostic/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC_V1

SPEC_ROUTE=DESIGN_SPEC. Exact owner atom: freeze and implement an offline
selection diagnostic, then stop before canonical scientific execution.

## Task Outcome Brief

- **Owner decision:** `censored_late` may not silently select on measured
  pre-decision X300; the diagnostic reports that selection or its absence on
  the frozen X surface only.
- **Product outcome:** reusable capability
  `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001` with frozen spec, typed
  terminals, and synthetic fail-closed tests. Canonical live run is out of
  this atom.
- **Named consumer:** HFIC post-`NO_WORTHY` router /
  `HFIC-SESS-560C4E1A72B4F9E6` identification blocker.
- **Cheapest falsifier:** synthetic fixtures in
  `tests/test_hfic_censoring_ignorability_diagnostic_v1.py` proving Y-point
  denial, denominator closure, permutation calibration, and typed terminals.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
- **Non-goals:** running the diagnostic on canonical active RDP; MAR /
  ignorability / identification claims; Y reads; provider calls; packet /
  ranker / quarantine / Critic / representation changes.
- **SPEC_ROUTE=DESIGN_SPEC**

## Frozen denominator (census-label readback, no Y values, not a diagnostic run)

Cohort `REL-20260902T111900Z-20260909T111900Z` /
`DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`.

| Class | Canonical rule | Count |
| --- | --- | --- |
| discovered-in-obs-partition | mint present in observation parquet | 610 |
| `X_ELIGIBLE` + `observed` | census `candidate_state=X_ELIGIBLE` and `denominator_state=observed` | 148 |
| `X_ELIGIBLE` + `censored_late` | same, `denominator_state=censored_late` | 327 |
| `ADMITTED` + `censored_late` | census `candidate_state=ADMITTED` | 35 |
| `X_POPULATION_INELIGIBLE` | census `candidate_state=X_POPULATION_INELIGIBLE` | 100 |

475 is exactly census `candidate_state=X_ELIGIBLE` (148+327). It is the
comparable X300 diagnostic subset. It is **not** a complete-pair outcome
denominator. Census `observed` is a membership label, not proof that every
Y point exists. The counts are bound to parquet SHA-256 and grouping SQL in
`docs/evidence/hfic_censoring_ignorability_diagnostic/a1_denominator_closure_v1.json`.
They are not a diagnostic receipt and cannot emit
`CANONICAL_COMPARABLE_X_SUBSET`: live release schemas still lack `dataset_id`
and `scientific_context_session`, and this spec has no file-hash pins.

The 35 `ADMITTED`/`censored_late` members have discovery timestamp and
inclusion probability, but `authoritative_anchor` is absent for all 35.
They remain visible in the receipt as
`CENSORING_NO_COMPARABLE_X300_ANCHOR_UNRESOLVED`. They are excluded from
the omnibus because they share no comparable X300 surface with the 475.

## Frozen X300 Block A (omnibus)

Usable on both groups, PIT = `point_id=X300` only, never any `Y*` point:

- `log1p(liquidity_usd)` from `FIELD-LIQUIDITY-USD-001` (DECIMAL, coverage 148/327)
- `log1p(market_cap_usd)` from `FIELD-MARKET-CAP-USD-001` (DECIMAL, 148/327)
- `log1p(usd_price)` from `FIELD-USD-PRICE-001` (DECIMAL, 148/327)
- `log1p(holder_count)` from `FIELD-HOLDER-COUNT-001` (DECIMAL, 147/326)
- `launchpad` from `FIELD-LAUNCHPAD-001` (TEXT, 148/327; levels with joint n<8 collapsed to `OTHER`)

Block B (descriptive only, not in omnibus): `first_pool_created_at` latency
relative to census `discovery_first_reliable_available_at`. Latency
definitionally feeds `censored_late` and would tautologically detect a shift.

Excluded from both blocks: TOKEN_MINT identity, FIRST-POOL-SOURCE (0/0),
STATS5M / R0-mix (coverage below the frozen 95% joint-observed floor), and
every `Y*` point.

Missing-X: per-feature pairwise deletion. A member stays in the 475 even if
one feature is missing. If any Block A feature has joint observed coverage
below 95% of 475, the run is `CENSORING_DIAGNOSTIC_INCONCLUSIVE`.

## Frozen algorithm

Pooled Cohen d for continuous features after frozen log1p. Variance ratio
`max(s1^2,s2^2)/min(s1^2,s2^2)` with zeros replaced by a tiny positive
epsilon only for the ratio denominator, never for means. Categorical
launchpad uses pairwise proportion SMD after rare-level collapse.

Omnibus statistic = `max(abs(SMD))` over Block A features that meet the
coverage floor. 1999 permutations of the 148/327 labels with seed `560C4E1A`
frozen before any statistic is computed. Two-sided Monte Carlo p =
`(1 + #{perm >= observed}) / (1 + 1999)`.

Terminals:

- `CENSORING_OBSERVED_X_SHIFT_DETECTED` iff observed max|SMD| >= 0.25 **and**
  permutation p <= 0.05. Complete-case 148 must not be treated as a random
  sample of `X_ELIGIBLE`.
- `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` iff those thresholds fail. This
  is **not** MAR, ignorability, or identification.
- `CENSORING_DIAGNOSTIC_INCONCLUSIVE` iff denominator, coverage, overlap, or
  integrity fails.

Overlap warning: if any Block A continuous feature has no overlapping
interquartile range, emit `SUPPORT_OVERLAP_WARNING` without upgrading the
terminal to identification.

## Decision capsule

- `DECISION_DELTA`: reusable X-only selection diagnostic, not a market test.
- `UNCERTAINTY_REMOVED`: frozen denominator, X inventory, and terminals.
- `CAPABILITY_OR_EVIDENCE`: capability + synthetic tests; no live scientific
  result in this atom.
- `STOP`: merge-readiness / owner phrase.
- `NEXT`: separately bounded atom that first adds frozen identity columns
  `dataset_id` and `scientific_context_session` to census/observations release
  schemas and pins those parquet SHA-256 values in the spec. Until both exist,
  any run remains `SYNTHETIC_OR_NONCANONICAL_POPULATION`. This merge does not
  authorize a scientific diagnostic against canonical active RDP.
