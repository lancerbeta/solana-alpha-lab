---
task_id: KCDN_ATOM_A_CANONICAL_BINDINGS_AND_DETERMINISTIC_NAVIGATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-25'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3a7018726a8ca2490222d9fb5d31798a9f5068fb
  expected_upstream: origin/main
  expected_upstream_oid: 3a7018726a8ca2490222d9fb5d31798a9f5068fb
  expected_branch: cursor/kcdn-atom-a-canonical-bindings
  dirty_mode: ALLOW_REPORTED
objective: Bind current Catalog semantic roots, make exact and conceptual search
  deterministic, add bounded related-asset navigation, and repair generated
  operator guidance so Project Sources is no longer the active discovery path.
managed_write_set:
- docs/tasks/KCDN_ATOM_A_CANONICAL_BINDINGS_AND_DETERMINISTIC_NAVIGATION_V1.md
- catalog/catalog_manifest.yaml
- catalog/schemas/catalog_manifest.schema.json
- catalog/query_recipes.yaml
- catalog/fixtures/discovery_gold_queries_v1.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- scripts/validate_catalog.py
- scripts/catalog_cli.py
- scripts/generate_navigation.py
- src/solana_alpha_lab/catalog_discovery.py
- tests/test_catalog_canonical_binding_discovery.py
- tests/test_catalog_search.py
- tests/test_generate_navigation.py
- tests/test_task34a_documentation_foundation.py
- tests/test_harness_sync.py
- docs/OPERATOR_NAVIGATION.md
- docs/PROJECT_MAP.md
- docs/evidence/kcdn_atom_a/a1_delivery_completion_evidence_v1.json
- docs/evidence/kcdn_atom_a/a1_delivery_independent_review_v1.json
- docs/evidence/kcdn_atom_a/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- ATOM_A2_OR_LATER
- RAG_VECTOR_OR_GRAPH_STORE
- SOURCE_RESOLVER_OR_COLLECTOR
- PROVIDER_API_RPC_WSS
- CONTEXT_MAP_OR_HARNESS_PIN
- MARKET_CONTEXT_V2_SEQUENCE
- MASS_SEARCH_TERM_REWRITE
- CRYSTALLIZATION_PACKET
- AUTOMATIC_NEXT_ATOM
context_requirements:
  catalog_asset_ids:
  - CATALOG-ROOT-001
  - CATALOG-CLI-001
  - GENERATOR-CATALOG-NAVIGATION-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-001-project-asset-catalog-baseline.md
    DELIVERY_EVIDENCE:
    - docs/evidence/kcdn_atom_a/a1_delivery_completion_evidence_v1.json
    - docs/evidence/kcdn_atom_a/a1_delivery_independent_review_v1.json
    - docs/evidence/kcdn_atom_a/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# KCDN_ATOM_A_CANONICAL_BINDINGS_AND_DETERMINISTIC_NAVIGATION_V1

## Task Outcome Brief

Make current Catalog roots resolvable by stable binding IDs, rank exact IDs
and paths above conceptual matches, traverse declared relations without a
graph store, and generate operator navigation from Git/Catalog/harness.

## Decision packet

- **DECISION_DELTA:** `ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY` binds
  `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010`;
  `ACTIVE-FACTORY-MARKET-FEATURE-SURFACE` binds
  `CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001`. Historical `v3`
  remains exact-resolvable and is not current.
- **UNCERTAINTY_REMOVED:** D1–D3 on `origin/main` `3a70187` — context-map
  still names registry v3; search was unsorted substring; operator nav
  presented Project Sources as the active path. Inspected PRD commit
  `a818ac7` is stale; no newer registry than `010` exists.
- **CAPABILITY_OR_EVIDENCE:** `resolve-binding`, ranked `search-assets`,
  `related-assets` depth ≤2, 24 gold queries, repaired `OPERATOR_NAVIGATION.md`.
- **STOP:** after this PR terminal and merge/read-back. No Atom A2/B/C/D/E.
- **NEXT:** owner-gated. Atom B is a harness pin, not this PR.
- **REPLAN_TRIGGER:** `BINDING_TARGET_AMBIGUOUS`,
  `DISCOVERY_METADATA_SCOPE_REPLAN`,
  `CATALOG_SCHEMA_BACKWARD_COMPATIBILITY_FAILED`,
  `CONTROL_PLANE_BLOCKED`.

## Non-goals

Atom A2 prior-work facade, context-map role pin, observable resolver,
collector, RAG/vector/graph, provider calls, Market Context V2/V2.1.

`CRYSTALLIZATION_PACKET=NONE` from upstream DESIGN_ONLY reports does not
block this atom. Do not create a crystallization packet here.
