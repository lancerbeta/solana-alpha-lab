---
intent_id: ARCH-INTENT-004
intent_version: '1.1'
status: IMPLEMENTED_BOUNDED_READ_ONLY_PROJECTION
as_of: '2026-08-14'
truth_owner: USER_GOAL_OWNER
projection_kind: DERIVED_READ_ONLY_PROJECTION
context_map_id: DELIVERY_CONTEXT_MAP_V1
truth_owners:
  bytes: GIT
  discovery_and_relations: CATALOG
  lifecycle: REGISTRIES
implementation: DELIVERY_HARNESS_V1
activation_evidence:
  - TWO_REPEATED_MANUAL_CONTEXT_RECONSTRUCTIONS
  - ENTRY_GATE_CONTEXT_RESOLUTION_MATERIAL_DELAY
authority:
  provider_read: false
  wallet_signer_transaction: false
  cash_spend: false
  project_source_mutation: false
contains_secrets: false
---

# ARCH-INTENT-004 — Factory Context Capsule and Workbench Boundary

The bounded Context Capsule is implemented as a deterministic read-only
projection through `DELIVERY_CONTEXT_MAP_V1`. It answers: what exact evidence,
constraints, prior relations and gaps apply to the named task and commit?

Git owns bytes, Catalog owns discovery/relations and registries own lifecycle.
The projection stores no second semantic truth. Every selected reference is
repository-relative and content-addressed; missingness is explicit. L0/L1 are
bounded working context, L2 is capability-triggered and L3 is dispute-driven
history.

The implementation deliberately excludes a graph/vector database, embeddings,
remote RAG, service, UI/workbench, provider calls, credentials, dependencies,
wallet/signer/transaction, cash, strategy logic, PnL and NetReturn. A future UI
remains trigger-gated by repeated owner questions and stable read contracts.

Cloud Project Sources are optional owner-managed export, not a projection truth
owner or activation gate.
