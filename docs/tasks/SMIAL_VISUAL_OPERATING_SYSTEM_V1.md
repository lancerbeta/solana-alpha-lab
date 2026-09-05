---
task_id: SMIAL_VISUAL_OPERATING_SYSTEM_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-05'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 89c9778f120c5d9cc68df340aa4339c75ea45b96
  expected_upstream: origin/main
  expected_upstream_oid: 89c9778f120c5d9cc68df340aa4339c75ea45b96
  expected_branch: cursor/smial-visual-operating-system-v1
  dirty_mode: ALLOW_REPORTED
objective: Canonize one durable SMIAL Visual Operating System so future owner-facing
  surfaces share presentation semantics without implementing Workbench, adopting a
  UI framework, or becoming a second domain-truth owner.
managed_write_set:
- docs/tasks/SMIAL_VISUAL_OPERATING_SYSTEM_V1.md
- docs/contracts/smial_visual_operating_system_v1.md
- configs/smial_visual_operating_system_v1.yaml
- catalog/schemas/smial_visual_operating_system.schema.json
- configs/factory_semantic_operability_v1.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- catalog/fixtures/discovery_gold_queries_v1.yaml
- docs/FACTORY_SEMANTIC_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/PROJECT_MAP.md
- tests/test_smial_visual_operating_system_v1.py
- tests/test_factory_semantic_operability.py
- tests/test_catalog_canonical_binding_discovery.py
- docs/evidence/smial_visual_operating_system/a1_delivery_completion_evidence_v1.json
- docs/evidence/smial_visual_operating_system/a1_delivery_independent_review_v1.json
- docs/evidence/smial_visual_operating_system/a1_delivery_factory_fit_v1.json
- docs/reports/smial_visual_operating_system/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- CURRENT_CANONICAL_VISUAL_OWNER_ALREADY_EXISTS
- MATERIAL_CONFLICT_WITH_NEWER_MAIN
- SECOND_TRUTH_STORE_REQUIRED
- NEW_UI_FRAMEWORK_REQUIRED
- CURRENT_WORKBENCH_REDESIGN_REQUIRED
- DOMAIN_STATE_CHANGE_REQUIRED
- AUTHORITY_SEMANTICS_CHANGE_REQUIRED
- PACKAGE_OR_FONT_ADOPTION_REQUIRED
- DEPLOYMENT_REQUIRED
- EXTERNAL_WRITE_REQUIRED
- CREDENTIAL_REQUIRED
- SEMANTIC_ROUTE_CANNOT_BE_ADDED_WITHOUT_BREAKING_CURRENT_ROUTING
- WALLET_SIGNER_TX_OR_CASH
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
    - docs/evidence/smial_visual_operating_system/a1_delivery_completion_evidence_v1.json
    - docs/evidence/smial_visual_operating_system/a1_delivery_independent_review_v1.json
    - docs/evidence/smial_visual_operating_system/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SMIAL_VISUAL_OPERATING_SYSTEM_V1

## SPEC_ROUTE

`BOTH` — owner packet is the PRD; this file is the exact Git task contract;
`docs/contracts/smial_visual_operating_system_v1.md` plus
`configs/smial_visual_operating_system_v1.yaml` are the durable design spec.

## DECISION_DELTA

Owner selected `STEEL SIGNAL` as the one SMIAL visual identity, with three
contextual sublanguages (`COMPUTATIONAL FIELD`, `EVIDENCE EDITORIAL`,
`CONTROL SURFACE`) that are not selectable themes. This atom records that
decision as Git-canonical presentation truth before Owner Workbench surface
area expands.

## UNCERTAINTY_REMOVED

A clean-clone agent can answer “how should an SMIAL owner-facing surface be
designed?” from Catalog / semantic routing without chat archaeology, and
without treating color, theme, or UI chrome as domain/authority truth.

## CAPABILITY_OR_EVIDENCE

Discoverable Visual Operating System: human companion, machine tokens/rules,
Catalog binding `ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM`, semantic route
`SEM-VISUAL-OPERATING-SYSTEM`, gold queries, generated navigation.

## NON-GOALS

No Workbench/Cockpit redesign; no UI framework, npm, component library, chart
package, font binary, Figma, theme engine, or light theme; no domain-state,
PAPER/SHADOW/LIVE, command-authority, Telegram-runtime, provider, VPS, or
deploy changes.

## ENTRY VERDICT

`START_AS_WRITTEN`

Rebind: observed Project Chat `main=a946e866...` moved through
`012d6f053f20a50dfa22ddc67b7e4c13df36a7a0` (PR #265) to
`origin/main=89c9778f120c5d9cc68df340aa4339c75ea45b96` via PR #266
(HOT90 runtime activation boundary). Ordinary merge of that main keeps HOT90
runtime truth and this atom's visual contract. No competing visual owner.

## FACTORY FIT / PRODUCT HORIZON

`NOW` because the owner inserted this atom before the Owner Workbench lane.
Value is lower UI drift and agent ambiguity. Does not establish alpha,
scientific evidence, trading readiness, runtime health, economics, or Owner
FCF.

`WATCH`: upcoming Owner Workbench Moves consume this contract.

After merge, recommended product resume remains
`OWNER_LIFECYCLE_PROJECTION_SPINE_V1` — do not auto-start.

## CHEAPEST FALSIFIER

Semantic gold queries for visual/UI/UX (EN+RU) resolve to
`SEM-VISUAL-OPERATING-SYSTEM` with `authority_granted=false`; domain questions
about open positions, current risk, runtime health, or PnL do not.

## DONE

`SMIAL_VISUAL_OPERATING_SYSTEM_V1_PASS` when the machine contract, Catalog
binding, semantic route, generated navigation, focused regressions, independent
review, Factory Fit, and exact-head CI/harness evidence are complete, with no
UI implementation and no new dependency.
