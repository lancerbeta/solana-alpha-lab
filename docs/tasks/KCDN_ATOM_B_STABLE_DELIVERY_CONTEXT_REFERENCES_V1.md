---
task_id: KCDN_ATOM_B_STABLE_DELIVERY_CONTEXT_REFERENCES_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-25'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: af0d5897c158ccd2114d19930555ba3b89397faf
  expected_upstream: origin/main
  expected_upstream_oid: af0d5897c158ccd2114d19930555ba3b89397faf
  expected_branch: cursor/kcdn-atom-b-stable-delivery-context
  dirty_mode: ALLOW_REPORTED
objective: Pin Delivery Harness role context by stable Catalog asset ID, keep
  historical path-only contracts valid, and remove the hardcoded provider
  registry v3 context-map dependency.
managed_write_set:
- docs/tasks/KCDN_ATOM_B_STABLE_DELIVERY_CONTEXT_REFERENCES_V1.md
- catalog/schemas/delivery_harness_task_contract.schema.json
- catalog/schemas/delivery_harness_context_receipt.schema.json
- scripts/delivery_harness.py
- delivery-harness/context-map.yaml
- delivery-harness/policies/solana-alpha-lab.md
- AGENTS.md
- delivery-harness/templates/portable-core/scripts/delivery_harness.py
- delivery-harness/templates/portable-core/delivery-harness/context-map.yaml
- delivery-harness/templates/portable-bundle-manifest.json
- docs/evidence/control/delivery_harness_acceptance_v1.json
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- tests/test_delivery_harness_stable_asset_references.py
- tests/test_delivery_harness_adapters.py
- docs/evidence/kcdn_atom_b/a1_delivery_completion_evidence_v1.json
- docs/evidence/kcdn_atom_b/a1_delivery_independent_review_v1.json
- docs/evidence/kcdn_atom_b/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- ATOM_A2_OR_LATER
- ATOM_C_OR_LATER
- RAG_VECTOR_OR_GRAPH_STORE
- SOURCE_RESOLVER_OR_COLLECTOR
- PROVIDER_API_RPC_WSS
- TWO_RUNG_LIVE_H900_V1
- MASS_ARCHIVE_TASK_MIGRATION
- AUTOMATIC_NEXT_ATOM
context_requirements:
  catalog_asset_ids:
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - CONFIG-DELIVERY-CONTEXT-MAP-001
  - SCRIPT-DELIVERY-HARNESS-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-005-direct-delivery-harness.md
    DELIVERY_EVIDENCE:
    - docs/evidence/kcdn_atom_b/a1_delivery_completion_evidence_v1.json
    - docs/evidence/kcdn_atom_b/a1_delivery_independent_review_v1.json
    - docs/evidence/kcdn_atom_b/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# KCDN_ATOM_B_STABLE_DELIVERY_CONTEXT_REFERENCES_V1

## Task Outcome Brief

New tasks pin semantic-role context by stable Catalog asset ID. Historical
path-only contracts stay valid. Context-map and domain guidance no longer treat
provider registry v3 as current.

## Decision packet

- **DECISION_DELTA:** optional `exact_role_asset_ids` on task contracts;
  `EXTERNAL_ROUTE_KNOWLEDGE` resolves through Catalog, not a hardcoded v3 path.
- **UNCERTAINTY_REMOVED:** a later current-binding move cannot rewrite an
  already-pinned task receipt; path-only fixtures remain unchanged.
- **CAPABILITY_OR_EVIDENCE:** asset-ID resolution with path/hash/method on the
  context receipt; binding-move invariant; no v3 path in current context guidance.
- **STOP:** after this PR terminal and merge/read-back. No Atom A2/C/D/E.
- **NEXT:** owner-gated.
- **REPLAN_TRIGGER:** Catalog resolution expands portable init beyond its
  declared boundary; receipt schema cannot stay backward compatible;
  `CONTROL_PLANE_BLOCKED`.

## Non-goals

Atom A2 prior-work facade, observable resolver, collector, RAG/vector/graph,
provider calls, mass archive task migration, TWO_RUNG_LIVE_H900_V1.
