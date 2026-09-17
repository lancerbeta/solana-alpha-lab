---
task_id: HFIC_SELECTION_ROBUSTNESS_GATE_V1
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
  expected_base: 503de99469f972fbabc10a6161159865df6d5d37
  expected_upstream: origin/main
  expected_upstream_oid: 503de99469f972fbabc10a6161159865df6d5d37
  expected_branch: cursor/hfic-selection-robustness-gate-impl-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Finish the HFIC post-NO_WORTHY selection boundary as one durable two-stage
  gate: reuse frozen Stage-1 CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001,
  add one fixed multivariate Block-A predictability falsifier, emit one typed
  router_decision, and consume that decision on ordinary Forge preflight
  without auto-Forge or a third diagnostic.

managed_write_set:
  - docs/tasks/HFIC_SELECTION_ROBUSTNESS_GATE_V1.md
  - configs/hfic_selection_robustness_gate_v1.yaml
  - configs/experiment_capability_registry_v2.yaml
  - src/solana_alpha_lab/factory/hfic_selection_robustness_gate.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_selection_robustness_gate_v1.py
  - tests/test_discovery_evidence_release_bridge.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/hfic_selection_robustness_gate/a1_owner_readout_v1.md
  - docs/evidence/hfic_selection_robustness_gate/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_selection_robustness_gate/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_selection_robustness_gate/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - CANONICAL_LIVE_CORPUS_GATE_RUN
  - STAGE1_FROZEN_SPEC_MUTATION
  - STAGE1_THRESHOLD_OR_RECEIPT_MUTATION
  - FEATURE_UNIVERSE_BROADENING
  - MODEL_OR_THRESHOLD_TUNING
  - THIRD_SELECTION_DIAGNOSTIC
  - GENERIC_ML_OR_WORKFLOW_ENGINE
  - AUTO_FORGE
  - Y_POINT_READ
  - PROVIDER_CALL
  - PACKET_BUDGET_CHANGE
  - RANKER_OR_SEARCH_BUDGET_CHANGE
  - CRITIC_OR_REPRESENTATION_CHANGE
  - HFIC_SESSION_QUARANTINE_OR_ERASURE
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
      - docs/evidence/hfic_selection_robustness_gate/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_selection_robustness_gate/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_selection_robustness_gate/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_SELECTION_ROBUSTNESS_GATE_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=DESIGN_SPEC.
DESIGN checkpoint verdict: `START_WITH_PATCH`.

Exact owner atom: implement the durable post-`NO_WORTHY` selection gate as
one PR, stop at merge-readiness. Do **not** run the canonical LIVE CORPUS
OPERATE in this atom.

## Task Outcome Brief

- **Owner decision:** observed vs `censored_late` membership on the Stage-1
  comparable X_ELIGIBLE population must not silently remain untested for
  multivariate predictability on the same frozen Block A surface. One typed
  `router_decision` tells ordinary Forge whether to block or proceed with an
  explicit caveat. A DETECTED / NOT_DETECTED / INCONCLUSIVE result after
  merge must not require another implementation PR merely to decide Forge.
- **Product outcome:** capability `CAP-HFIC-SELECTION-ROBUSTNESS-GATE-001`
  composing frozen Stage 1 then one L2-logistic OOF-AUC falsifier, plus a
  pure router and a minimal Forge-preflight consumption seam.
- **Named consumer:** ordinary `/hypothesis-forge` preflight after
  `HFIC-SESS-560C4E1A72B4F9E6` / post-`NO_WORTHY` identification blocker.
- **Cheapest falsifier:** synthetic tests proving Stage-1 freeze, skip/run
  routing, exact Block A universe, leakage denial, fold-local preprocessing,
  seed replay, DETECTED/NOT_DETECTED/INCONCLUSIVE terminals, Forge mapping,
  no Y/provider/credential access, and CI independence from machine-local
  LIVE CORPUS.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
  Canonical OPERATE is a later bounded atom.
- **Non-goals:** live corpus run; Stage-1 YAML/SHA/threshold/receipt edits;
  STATS5M/R0/quote/Y/timing/identity features; model search; third diagnostic;
  auto-Forge; Critic/representation/ranker/search-budget edits; quarantining
  prior HFIC sessions.

## Frozen scientific question (Stage 2)

Can observed vs `censored_late` membership be materially predicted
out-of-sample by a linear combination of the SAME pre-decision X300 Block A
surface that passed Stage 1?

This is a multivariate robustness check of the measured-X surface. It is not
an MNAR model, not MAR/ignorability/identification, not a market hypothesis.

## Population

Exactly Stage 1 comparable population: `candidate_state == X_ELIGIBLE`,
observed=148, censored_late=327, N=475 on the canonical corpus. Exclude the
35 ADMITTED/no-X300, X_POPULATION_INELIGIBLE, discovery exclusions, and all Y.
No population redefinition.

## Feature universe

Exactly Stage-1 Block A:

- `FIELD-USD-PRICE-001`
- `FIELD-LIQUIDITY-USD-001`
- `FIELD-MARKET-CAP-USD-001`
- `FIELD-HOLDER-COUNT-001`
- `FIELD-LAUNCHPAD-001`

Hard exclude TOKEN_MINT/identity, FIRST_POOL_CREATED_AT, FIRST_SEEN_AT,
FIRST_POOL_SOURCE, all STATS5M, R0, all FIELD-QUOTE-*, any Y*, HTTP/provider
timing/hash/missing_reason metadata, anything not proven PIT at X300.

## Model / falsifier

One L2-regularized logistic regression, `l2_lambda = 1.0`, no tuning.
Five-fold stratified seeded CV, fold-local preprocessing. Primary statistic
`OOF_ROC_AUC`. DETECTED requires AUC >= 0.57 **and** permutation p <= 0.05
(999 perms, seed `A17C9E02`, Monte Carlo `(1+hits)/(1+999)`).

AUC 0.57 is the directly frozen practical discrimination floor, chosen to
stay on approximately the same practical effect scale as Stage-1 d=0.25.
It is **not** claimed to be mathematically equivalent to Cohen d=0.25.

## Router

| Stage 1 | Stage 2 | `router_decision` |
| --- | --- | --- |
| `CENSORING_OBSERVED_X_SHIFT_DETECTED` | skip | `BLOCK_FORGE_SELECTION_RISK` |
| `CENSORING_DIAGNOSTIC_INCONCLUSIVE` | skip | `BLOCK_FORGE_EVIDENCE_GAP` |
| unknown / integrity-invalid | skip | `BLOCK_FORGE_EVIDENCE_GAP` |
| `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` | `SELECTION_PREDICTABILITY_DETECTED` | `BLOCK_FORGE_SELECTION_RISK` |
| `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` | `SELECTION_PREDICTABILITY_INCONCLUSIVE` | `BLOCK_FORGE_EVIDENCE_GAP` |
| `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` | `SELECTION_PREDICTABILITY_NOT_DETECTED` | `FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT` |

`FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT` means ordinary Forge may be invoked
while residual unmeasured-selection uncertainty is carried as a limitation.
It does not prove identification.

## Delivery notes

- `DECISION_DELTA`: durable two-stage selection gate with one Forge-facing
  `router_decision`.
- `UNCERTAINTY_REMOVED`: operator no longer combines Stage-1/Stage-2 by hand;
  Forge preflight consumes the typed decision only when the receipt matches
  the current canonical corpus binding (`dataset_manifest_id` included).
- `CAPABILITY_OR_EVIDENCE`: `CAP-HFIC-SELECTION-ROBUSTNESS-GATE-001` +
  synthetic proofs. Canonical LIVE CORPUS result is out of this atom.
- `STOP`: merge-readiness / exact owner phrase. No guarded merge without
  the current owner phrase. No canonical OPERATE here.
- `NEXT`: after merge + post-merge readback, one separately bounded OPERATE
  `selection-robustness-gate`.
- `REPLAN_TRIGGER`: Stage-1 semantics drift on `origin/main`; inability to
  keep Block A frozen; need for STATS5M/R0 as a new estimand.
- `SPEC_ROUTE=DESIGN_SPEC`
