---
task_id: SCIENCE_TO_STRATEGY_HANDOFF_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-06"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: dc44aca566ab141c641700d5cf6e8e8ddcdc77b9
  expected_upstream: origin/main
  expected_upstream_oid: dc44aca566ab141c641700d5cf6e8e8ddcdc77b9
  expected_branch: cursor/science-to-strategy-handoff-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Freeze a typed decision-time promotion handoff manifest on new scientific
  PROMOTE events and expose a derived ScienceToStrategyHandoffV1 path that can
  deterministically render a StrategyVersion v1.1 candidate without activating
  PAPER/SHADOW/LIVE, inventing risk defaults, or rewriting history.
managed_write_set:
  - docs/tasks/SCIENCE_TO_STRATEGY_HANDOFF_V1.md
  - docs/contracts/science_to_strategy_handoff_v1.md
  - docs/contracts/experiment_evidence_decision_v1.md
  - docs/contracts/owner_lifecycle_projection_spine_v1.md
  - docs/contracts/research_lifecycle_workbench_v1.md
  - catalog/schemas/promotion_handoff_manifest_v1.schema.json
  - src/solana_alpha_lab/factory/promotion_handoff.py
  - src/solana_alpha_lab/factory/experiment_evidence.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/lifecycle_projection.py
  - src/solana_alpha_lab/factory/research_workbench.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/owner_language.py
  - tests/test_science_to_strategy_handoff_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_experiment_evidence_decision_v1.py
  - tests/test_factory_semantic_operability.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/schemas/factory_semantic_operability.schema.json
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - README.md
  - configs/ci_test_shards_v1.json
  - docs/evidence/science_to_strategy_handoff/a1_delivery_completion_evidence_v1.json
  - docs/evidence/science_to_strategy_handoff/a1_delivery_independent_review_v1.json
  - docs/evidence/science_to_strategy_handoff/a1_delivery_factory_fit_v1.json
  - docs/reports/science_to_strategy_handoff/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PREDECESSOR_NOT_CANONICALLY_INTEGRATED
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - SEMANTIC_ROUTE_OWNERSHIP_AMBIGUOUS
  - PROMOTE_PROVENANCE_REQUIRES_INFERENCE
  - HISTORICAL_RESEARCHSTORE_REWRITE_REQUIRED
  - EVIDENCE_SNAPSHOT_SEMANTICS_MUST_CHANGE
  - STRATEGY_VERSION_V1_1_INSUFFICIENT
  - EXECUTION_RISK_DEFAULTS_REQUIRED
  - RELATION_REQUIRES_FILENAME_TIME_OR_TEXT_INFERENCE
  - WORKBENCH_MUST_BECOME_GIT_WRITER
  - DEPLOYMENT_OR_LIVE_OPERATION_REQUIRED
  - PROVIDER_CREDENTIAL_WALLET_OR_SPEND_REQUIRED
  - NEW_DB_SERVICE_OR_WORKFLOW_ENGINE_REQUIRED
  - REPEATED_MATERIAL_BLOCKER
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - docs/contracts/experiment_evidence_decision_v1.md
      - docs/contracts/owner_lifecycle_projection_spine_v1.md
      - catalog/schemas/strategy_version_v1_1.schema.json
    DELIVERY_EVIDENCE:
      - docs/evidence/science_to_strategy_handoff/a1_delivery_completion_evidence_v1.json
      - docs/evidence/science_to_strategy_handoff/a1_delivery_independent_review_v1.json
      - docs/evidence/science_to_strategy_handoff/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SCIENCE_TO_STRATEGY_HANDOFF_V1

## SPEC_ROUTE

`BOTH` — this file is the exact Git task contract;
`docs/contracts/science_to_strategy_handoff_v1.md` is the durable handoff
contract. No new semantic route. No second truth store.

## ENTRY VERDICT

`START_WITH_PATCH`

Fresh Git:

- `origin/main` = `7b7f96d191b12fb37a90565241b0ce0c447eaf30`
- predecessor `FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1` = PR #272 MERGED;
  post-merge CI SUCCESS on that exact main head
- `OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1` = PR #271 MERGED (`2eae71b9`),
  ancestor of current main
- Move 2 `EXPERIMENT_EVIDENCE_DECISION_V1` = PR #270 MERGED
- no due active time gate
- `SEM-OWNER-LIFECYCLE` resolves unambiguously

PATCH reason: Move 2 PROMOTE and StrategyVersion v1.1 already exist. The
missing capability is a frozen decision-time handoff plus an owner-visible
materialization path that does not invent defaults or activate runtime.

## DECISION_DELTA

New PROMOTE events freeze a typed `promotion_handoff_manifest` v1.0 inside
the scientific decision payload. A derived `ScienceToStrategyHandoffV1`
projects handoff state and can CHECK/RENDER/VERIFY a StrategyVersion v1.1
candidate. Workbench shows the bottleneck in Russian. Git remains the
StrategyVersion writer; Workbench does not commit.

## UNCERTAINTY_REMOVED

Petr can see whether a scientific PROMOTE exists, what evidence it froze,
whether a StrategyVersion can be formed honestly, the one real blocker if
not, and that nothing was launched.

## CAPABILITY_OR_EVIDENCE

Three vertical loops on one synthetic contract-real fixture: science freeze,
deterministic materialization, owner/agent legibility.

## NON-GOALS

No StrategyVersion v1.2; no fake production strategy under
`configs/strategies`; no activation/PAPER/SHADOW/LIVE; no VPS; no new
database, workflow engine, risk-profile platform, or owner science-edit UI.

## MODEL_EFFORT_RECOMMENDATION

`SOL_XHIGH`

## CHEAPEST FALSIFIER

ExperimentSpec → DIRECT evidence → PROMOTE with hashed manifest → later
evidence does not rewrite the manifest → missing execution inputs block
rather than default → identical inputs render an identical v1.1 candidate →
`/research` shows Russian status without Git mutation.

## PRODUCT HORIZON

`NOW`: SCIENCE_TO_STRATEGY_HANDOFF_V1
`WATCH`: TRADING_OPERATIONS_WORKBENCH_V2 — trigger when a StrategyVersion
needs owner-visible strategy→bot→position operation. Do not auto-start.
