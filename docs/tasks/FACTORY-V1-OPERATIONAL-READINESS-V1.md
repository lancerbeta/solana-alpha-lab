---
task_id: FACTORY-V1-OPERATIONAL-READINESS-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DESIGN_ONLY, DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 084d311596b35bea3cf156360b81e65b47c62b92
  expected_upstream: origin/main
  expected_upstream_oid: 084d311596b35bea3cf156360b81e65b47c62b92
  expected_branch: cursor/factory-v1-operational-readiness
  dirty_mode: ALLOW_REPORTED
objective: Canonize Factory v1 operational readiness as an accepted Git-native product direction without implementing cockpit, runner, runtime, or a numbered task chain.
managed_write_set:
  - docs/tasks/FACTORY-V1-OPERATIONAL-READINESS-V1.md
  - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
  - configs/factory_v1_operational_readiness_v1.yaml
  - tests/test_factory_v1_operational_readiness.py
  - tests/test_catalog.py
  - catalog/schemas/asset_catalog.schema.json
  - scripts/validate_catalog.py
  - catalog/assets/architecture.yaml
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_operational_readiness/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_operational_readiness/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_operational_readiness/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PRODUCT_IMPLEMENTATION
  - NUMBERED_TASK_CHAIN_INSERTION
  - HISTORICAL_PROJECT_SOURCES_ROADMAP_MUTATION
  - HISTORICAL_EVIDENCE_MUTATION
  - DOMAIN_POLICY_HASH_BOUND_MUTATION
  - PROVIDER_OR_NETWORK_CALL
  - UI_FRAMEWORK_SELECTION
  - WALLET_SIGNER_TX_OR_CASH
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-002
    - ARCH-INTENT-004
    - ARCH-INTENT-005
    - ARCH-INTENT-T21-PRODUCT-VISION-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-002-hypothesis-factory-operating-model.md
      - docs/architecture/intents/ARCH-INTENT-003-product-owner-operating-topology.md
      - docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_v1_operational_readiness/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_v1_operational_readiness/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_v1_operational_readiness/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY-V1-OPERATIONAL-READINESS-V1

## Task Outcome Brief

- **Owner decision:** the missing product is the operating surface around
  existing Factory truth, not another research framework. Land that direction
  as Git-canonical intent plus a triggered milestone contract.
- **Product outcome:** `FACTORY_V1_OPERATIONAL_READY` exists as
  `NOT_TRIGGERED`. No cockpit, runner, VPS, UI framework, or numbered
  successor tasks are created.
- **Named consumers:** `GOAL_OWNER`, Entry Gate, Factory Fit, later
  productization atoms.
- **Cheapest falsifier:** the artifact claims implementation, inserts a
  numbered task chain, mutates historical Project Sources roadmaps, or
  substitutes infrastructure inventory for a commissioning run.
- **Terminal outcome:** `PROCEED` if the intent and YAML are Catalog-bound,
  tests prove non-implementation and the triggered-milestone contract, and
  historical receipts stay untouched.
- **User-visible result:** one architecture intent and one machine-readable
  readiness contract. The owner can later trigger productization without
  archaeology of this chat.
- **Non-goals:** no Owner Cockpit, experiment runner, production-lite
  runtime, monitoring product, paper/shadow operations, real-money
  execution, UI framework selection, provider/network/cash, domain-policy
  byte mutation, or historical evidence rewrite.
- **Evidence budget:** offline repository work; targeted tests only; no
  local full gate before PR.
- **Replan trigger:** a cheaper live market falsifier must run first, or
  domain-policy mutation is later authorized together with its hash-bound
  historical receipts.

## Decision capsule

- `DECISION_DELTA`: Factory v1 readiness is a triggered product milestone,
  not a chain of numbered platform tasks.
- `UNCERTAINTY_REMOVED`: "ready" means owner-operable hypothesis cycle
  through reusable Factory capabilities, not profit or Alpha/Execution Fit.
- `CAPABILITY_OR_EVIDENCE`: Git-canonical `ARCH-INTENT-005` plus
  `FACTORY_V1_OPERATIONAL_READY=NOT_TRIGGERED`.
- `STOP`: no product implementation and no historical roadmap/evidence
  rewrite.
- `NEXT`: keep the current cheapest decision-bearing market falsifier
  unless the owner explicitly selects Factory productization.
- `SPEC_ROUTE`: `BOTH`
- `MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
- `REPLAN_TRIGGER`: productization preempts an active cheaper market
  falsifier, or a commissioning hypothesis requires a new bespoke pipeline.

## Live roadmap binding

Harness `PRODUCT_ROADMAP` is per-task `roadmap_path`. This contract binds
`configs/factory_v1_operational_readiness_v1.yaml`. Historical Project
Sources roadmaps are not modified. No numbered task chain is inserted.

## Domain-policy integration

The requested invariant is recorded in the intent and YAML. The live domain
policy file is not mutated in this atom because current tests bind its bytes
to historical harness-bootstrap and TASK-30 A20R1 receipts. Existing
`FACTORY_LEVERAGE_INVARIANT` already covers post-readiness composition
defaults.

## Definition of Done

1. `ARCH-INTENT-005` is Catalog-resolvable and
   `ACCEPTED_DIRECTION_NOT_IMPLEMENTED`.
2. The YAML contract names `FACTORY_V1_OPERATIONAL_READY=NOT_TRIGGERED`,
   the commissioning gate, and activation triggers.
3. Generated navigation includes the new assets.
4. Targeted tests prove non-implementation, truth-owner preservation, and
   no numbered-task insertion.
5. Historical Project Sources roadmaps, frozen hypotheses, consumed
   holdouts, and historical evidence bytes are unchanged.
