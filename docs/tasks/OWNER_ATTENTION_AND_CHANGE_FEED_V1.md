---
task_id: OWNER_ATTENTION_AND_CHANGE_FEED_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-07"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ac5c91c3baab36c055ab0e48dbd0ae4d37de2ac4
  expected_upstream: origin/main
  expected_upstream_oid: ac5c91c3baab36c055ab0e48dbd0ae4d37de2ac4
  expected_branch: cursor/owner-attention-and-change-feed-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make HOME one owner daily composition of source-local Research,
  Operations and System attention plus native change history and a
  hash-bound OwnerReviewCursorV1, without an attention database,
  notification platform, or Git snapshots of current attention.
managed_write_set:
  - docs/tasks/OWNER_ATTENTION_AND_CHANGE_FEED_V1.md
  - docs/contracts/owner_attention_and_change_feed_v1.md
  - src/solana_alpha_lab/factory/owner_daily_attention.py
  - src/solana_alpha_lab/factory/owner_review_cursor.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/owner_language.py
  - tests/test_owner_attention_and_change_feed_v1.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_catalog_canonical_binding_discovery.py
  - tests/test_owner_lifecycle_projection_spine_v1.py
  - catalog/schemas/factory_semantic_operability.schema.json
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - README.md
  - docs/evidence/owner_attention_and_change_feed/a1_delivery_completion_evidence_v1.json
  - docs/evidence/owner_attention_and_change_feed/a1_delivery_independent_review_v1.json
  - docs/evidence/owner_attention_and_change_feed/a1_delivery_factory_fit_v1.json
  - docs/reports/owner_attention_and_change_feed/a1_owner_readout_v1.md
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
  - SOURCE_LOCAL_ATTENTION_OWNER_AMBIGUOUS
  - HOME_MUST_CRAWL_STORES_DIRECTLY
  - CHANGE_HISTORY_REQUIRES_SNAPSHOT_DIFF
  - DEDUP_REQUIRES_FUZZY_OR_LLM
  - PRIORITY_REQUIRES_INVENTED_SLO
  - REVIEW_CURSOR_REQUIRES_DB_OR_SERVICE
  - SYSTEM_V2_REQUIRED_FOR_VALUE
  - PRODUCT_DELIVERY_ATTENTION_COLLISION
  - PROVIDER_CREDENTIAL_WALLET_OR_SPEND_REQUIRED
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
      - docs/contracts/owner_attention_and_change_feed_v1.md
      - docs/contracts/trading_operations_workbench_v2.md
      - docs/contracts/research_lifecycle_workbench_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/owner_attention_and_change_feed/a1_delivery_completion_evidence_v1.json
      - docs/evidence/owner_attention_and_change_feed/a1_delivery_independent_review_v1.json
      - docs/evidence/owner_attention_and_change_feed/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OWNER_ATTENTION_AND_CHANGE_FEED_V1

## SPEC_ROUTE

`BOTH` — this file is the exact Git task contract;
`docs/contracts/owner_attention_and_change_feed_v1.md` is the durable
product contract. One new semantic route `SEM-OWNER-DAILY-ATTENTION`.

## ENTRY VERDICT

`START_WITH_PATCH`

Fresh Git:

- live `origin/main` = `ac5c91c3baab36c055ab0e48dbd0ae4d37de2ac4`
  (PR #276 TRADING_OPERATIONS_WORKBENCH_V2 is canonical on main)
- no due unresolved active-time gate
- Research Workbench, TradingOperationsProjectionV2, HOME/Cockpit and
  Visual OS attention language already exist
- semantic route budget was 12; Move 5 adds exactly one product route
  and raises the closed max to 13

## DECISION_DELTA

HOME becomes the daily owner composition, not a second dashboard and
not a notification platform.

## UNCERTAINTY_REMOVED

Whether Petr must sweep Research / Operations / System to learn if
anything requires him.

## CAPABILITY_OR_EVIDENCE

OwnerAttentionProjectionV1 + OwnerReviewCursorV1 + SEM-OWNER-DAILY-ATTENTION.

## STOP

Merge-readiness owner phrase. Do not start SYSTEM_OPERABILITY_SURFACE_V2.

## NEXT

WATCH = SYSTEM_OPERABILITY_SURFACE_V2 after owner use, not automatically.

## DoD

See the owner EXECUTE packet section 39. PASS only when vertical A/B/C,
read-safety, semantic Git and isolated CODE/GOAL/ARCHITECTURE plus
Factory Fit FULL_REVIEW reach the merge gate.
