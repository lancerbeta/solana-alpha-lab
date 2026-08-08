---
intent_id: ARCH-INTENT-004
intent_version: '1.0'
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
as_of: '2026-08-08'
truth_owner: USER_GOAL_OWNER
projection_kind: DERIVED_READ_ONLY_PROJECTION
truth_owners:
  bytes: GIT
  discovery_and_relations: CATALOG
  lifecycle: REGISTRIES
implementation: DEFERRED_UNTIL_TRIGGER
activation_triggers_any:
  - TASK28_FIRST_NONEMPTY_HYPOTHESIS_OR_SECOND_REAL_HYPOTHESIS
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

## Purpose

This accepted direction defines the boundary for a future Factory Context Capsule and Research Workbench navigation surface. Before a hypothesis is started or extended, its question is: **what evidence, constraints, prior attempts, and next safe action already exist?**

The direction supports navigation only. It does not implement a Capsule, research workflow, execution route, strategy, or owner decision.

## Intended future read model

When and only when an activation trigger is observed, a separate Entry Gate may consider a deterministic, read-only projection that returns:

- stable asset IDs, repository paths, content hashes, and named consumers;
- lifecycle state and evidence-linked missingness; and
- explicit `UNKNOWN` or `CATALOG_GAP` outcomes instead of reconstructed context or semantic inference.

Git remains the truth owner for bytes, the Catalog for discovery and relationships, and lifecycle registries for lifecycle truth. The projection must never become a second truth owner or silently rewrite any of those owners.

## Explicit exclusions

`ADR-001` keeps a graph database deferred until measured need. This direction also excludes vector databases, embeddings, RAG services, remote services, user interfaces, provider/API/RPC/WSS calls, dependencies, wallets, signers, transactions, cash, strategy logic, PnL, NetReturn, and Project Source mutation.

## Activation and falsification

The future projection stays deferred until any one declared activation trigger is observed:

1. `TASK28_FIRST_NONEMPTY_HYPOTHESIS_OR_SECOND_REAL_HYPOTHESIS`;
2. `TWO_REPEATED_MANUAL_CONTEXT_RECONSTRUCTIONS`; or
3. `ENTRY_GATE_CONTEXT_RESOLUTION_MATERIAL_DELAY`.

The cheapest falsifier is an existing bounded Catalog/lifecycle query: if it clearly answers the next owner decision, no Capsule should be built. A separate Entry Gate is required before any implementation, even after a trigger.
