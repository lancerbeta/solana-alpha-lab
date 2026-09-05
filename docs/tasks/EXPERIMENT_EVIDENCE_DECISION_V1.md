---
task_id: EXPERIMENT_EVIDENCE_DECISION_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-06"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9ce5f80e775ce1e7bacf9383e3dd4412501f88d6
  expected_upstream: origin/main
  expected_upstream_oid: 9ce5f80e775ce1e7bacf9383e3dd4412501f88d6
  expected_branch: cursor/experiment-evidence-decision-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Turn one existing experiment into a Russian-first owner loop over
  LifecycleProjectionV1 and ResearchStore: understand definition and
  explicit evidence, record a bounded scientific DECISION_EVENT, and
  read it back without Git archaeology, a second truth store, or
  StrategyVersion materialization.
managed_write_set:
  - docs/tasks/EXPERIMENT_EVIDENCE_DECISION_V1.md
  - docs/tasks/RESEARCH_LIFECYCLE_WORKBENCH_V1.md
  - docs/contracts/experiment_evidence_decision_v1.md
  - docs/contracts/research_lifecycle_workbench_v1.md
  - docs/contracts/smial_visual_operating_system_v1.md
  - docs/reports/research_lifecycle_workbench/a1_owner_readout_v1.md
  - src/solana_alpha_lab/factory/owner_language.py
  - src/solana_alpha_lab/factory/experiment_evidence.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/research_workbench.py
  - src/solana_alpha_lab/factory/workbench.py
  - tests/test_experiment_evidence_decision_v1.py
  - tests/test_research_lifecycle_workbench_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/experiment_evidence_decision/a1_delivery_completion_evidence_v1.json
  - docs/evidence/experiment_evidence_decision/a1_delivery_independent_review_v1.json
  - docs/evidence/experiment_evidence_decision/a1_delivery_factory_fit_v1.json
  - docs/reports/experiment_evidence_decision/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - MOVE1_NOT_CANONICAL
  - PREDECESSOR_SEMANTIC_CONFLICT_NOT_SAFELY_PATCHABLE
  - CANONICAL_EVIDENCE_OWNER_CONFLICT
  - DIRECT_EVIDENCE_REQUIRES_GUESSING
  - HOLDOUT_OWNER_UNRESOLVED_AND_PROMOTION_DEPENDS_ON_IT
  - RESEARCHSTORE_DECISION_REQUIRES_MAJOR_DATA_PLANE_REWRITE
  - NEW_DATABASE_REQUIRED
  - NEW_BACKGROUND_SERVICE_REQUIRED
  - NEW_FRONTEND_FRAMEWORK_REQUIRED
  - STRATEGY_CREATION_REQUIRED
  - CURRENT_AUTHORITY_SEMANTICS_MUST_WEAKEN
  - DEPLOYMENT_REQUIRED
  - PROVIDER_CALL_REQUIRED
  - CREDENTIAL_REQUIRED
  - WALLET_OR_REAL_MONEY_REQUIRED
  - LOCALIZATION_SCOPE_ESCAPE
  - REPEATED_MATERIAL_BLOCKER
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
    - docs/evidence/experiment_evidence_decision/a1_delivery_completion_evidence_v1.json
    - docs/evidence/experiment_evidence_decision/a1_delivery_independent_review_v1.json
    - docs/evidence/experiment_evidence_decision/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EXPERIMENT_EVIDENCE_DECISION_V1

## SPEC_ROUTE

`BOTH` — owner packet is the PRD; this file is the exact Git task contract;
`docs/contracts/experiment_evidence_decision_v1.md` is the durable human
contract. No second machine projection schema. No new semantic route.

## DECISION_DELTA

Move 2 / Decision Compression: `/research` experiment detail becomes a
decision dossier. Owner-facing copy is Russian-first. Machine/scientific
contracts stay canonical English. `PROMOTE` appends scientific
`DECISION_EVENT` only.

## UNCERTAINTY_REMOVED

Petr can select a real experiment, see what was tested versus what
evidence exists, distinguish DIRECT vs RELATED, record REJECT/REVISE/
PAUSE/PROMOTE against a stale-safe snapshot, and read the committed
decision back without Git/SSH/SQLite archaeology.

## CAPABILITY_OR_EVIDENCE

Typed experiment-evidence composition over existing ResearchStore
record kinds and LifecycleProjection; FactoryApplication decision
command with readback; Russian presentation layer; SEM-OWNER-LIFECYCLE
extension; Move-1 stale completion metadata repair.

## NON-GOALS

No StrategyVersion / PAPER / SHADOW / LIVE; no new database, service,
frontend framework, or i18n stack; no runtime LLM translation; no
rewrite of legacy scientific corpus; no VPS deploy; no README/AGENTS
edit unless front-door semantics would become false.

## ENTRY VERDICT

`START`

Revalidated `origin/main=9ce5f80e775ce1e7bacf9383e3dd4412501f88d6`
(PR #269 merged). Post-merge CI of Move 1 is the predecessor close.
Move-1 task status `IN_PROGRESS` with placeholder HEAD/PR is stale
completion metadata and is patched in this write set.

## FACTORY FIT / PRODUCT HORIZON

`NOW` because Move 1 is on main and the owner still cannot compress
one experiment into a research decision without archaeology.

`WATCH`: `SCIENCE_TO_STRATEGY_HANDOFF_V1`. Do not auto-start.

## CHEAPEST FALSIFIER

Real `EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001` renders truthfully
incomplete; a disposable ResearchStore records one decision with
readback; PROMOTE fails closed when required evidence is missing;
GET `/research` remains non-mutating.

## DONE

`EXPERIMENT_EVIDENCE_DECISION_V1_PASS` when slices A/B/C, language
policy `OWNER_LANGUAGE_RU_PASS`, isolated critics, Factory Fit, and
exact-head CI/harness evidence are complete.
