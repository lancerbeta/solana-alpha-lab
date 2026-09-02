---
task_id: FACTORY_SEMANTIC_OPERABILITY_CLOSURE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ba18dc4b76e644aa0078fdeefd3d0e130432e634
  expected_upstream: origin/main
  expected_upstream_oid: ba18dc4b76e644aa0078fdeefd3d0e130432e634
  expected_branch: cursor/factory-semantic-operability-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Close semantic operability with a bounded Catalog-backed route
  projection so a clean-clone agent can locate current capability roots without
  archaeology, without granting authority or caching runtime state.
managed_write_set:
- docs/tasks/FACTORY_SEMANTIC_OPERABILITY_CLOSURE_V1.md
- configs/factory_semantic_operability_v1.yaml
- catalog/schemas/factory_semantic_operability.schema.json
- catalog/schemas/catalog_manifest.schema.json
- catalog/catalog_manifest.yaml
- catalog/query_recipes.yaml
- catalog/fixtures/discovery_gold_queries_v1.yaml
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- src/solana_alpha_lab/catalog_discovery.py
- src/solana_alpha_lab/factory_semantic_operability.py
- scripts/catalog_cli.py
- scripts/generate_navigation.py
- docs/FACTORY_SEMANTIC_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/PROJECT_MAP.md
- README.md
- AGENTS.md
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_session.py
- .agents/skills/hypothesis-forge/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_factory_semantic_operability.py
- tests/test_catalog_canonical_binding_discovery.py
- tests/test_catalog_search.py
- tests/test_generate_navigation.py
- tests/test_hfic_preflight.py
- tests/test_hfic_operational_closure_v1.py
- tests/test_task34a_documentation_foundation.py
- docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/evidence/control/a1_merge_readiness_before_owner_phrase_completion_v1.json
- docs/evidence/factory_semantic_operability_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_semantic_operability_closure/a1_delivery_independent_review_v1.json
- docs/evidence/factory_semantic_operability_closure/a1_delivery_factory_fit_v1.json
- docs/reports/factory_semantic_operability_closure/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- SEMANTIC_LAYER_REQUIRES_SECOND_TRUTH_STORE
- SEMANTIC_ROUTE_CANNOT_BE_DERIVED_FROM_EXISTING_TRUTH
- CURRENT_ROOT_AMBIGUOUS_MATERIAL
- CATALOG_SCHEMA_BACKWARD_COMPATIBILITY_BREAK
- HFIC_SEARCH_BUDGET_SEMANTICS_CORRUPTED
- FORGE_PACKET_BUDGET_CANNOT_BE_PRESERVED
- AUTHORITY_INFERENCE_CANNOT_BE_FAIL_CLOSED
- CONTROL_PLANE_CHANGE_BECOMES_REQUIRED
- WALLET_BUILD_EXECUTE_TRANSACTION
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
    - docs/evidence/factory_semantic_operability_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_semantic_operability_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_semantic_operability_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_SEMANTIC_OPERABILITY_CLOSURE_V1

## SPEC_ROUTE

`BOTH` — PRD + SSD in the owner execution packet; this file is the exact Git
task contract.

## DECISION_DELTA

Add one bounded semantic-operability surface over existing Catalog truth so a
clean-clone agent routes ordinary product/capability questions to current Git
roots without archaeology or a second knowledge platform.

## UNCERTAINTY_REMOVED

Whether Git/Catalog already supplies enough structured truth for agent-first
product navigation. Expected answer: yes — only a bounded semantic facade was
missing.

## CAPABILITY_OR_EVIDENCE

Validated semantic routing projection consumed by fresh agents, GOAL_OWNER
orientation, Hypothesis Forge context, and future agentic capability discovery.

## NON-GOALS

No RAG/embeddings/vector/graph DB; no autonomous Hypothesis Generator; no
provider/VPS/deploy/Drive mutation; no roadmap replacement; no Catalog
replacement; no Delivery Context Capsule replacement; no historical task
rewrite; no recreation of the missing historical roadmap file.

## DONE

`FACTORY_SEMANTIC_OPERABILITY_CLOSURE_PASS` with the machine packet from the
execution contract (clean-clone gold routes, authority_granted=false, runtime
non-fabrication, Forge semantic bytes/digest bounds, Catalog regressions).
