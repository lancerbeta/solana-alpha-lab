---
task_id: FORGE_TRUST_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-10'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 90ba76e37515b3d521478a6d05a149fb0f1d2b75
  expected_upstream: origin/main
  expected_upstream_oid: 90ba76e37515b3d521478a6d05a149fb0f1d2b75
  expected_branch: codex/forge-trust-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair and requalify the implemented Forge producer-to-owner vertical in synthetic scope, preserving current read freshness, exact execution identity, scientific guards, history and recovery; resolve BAA-003 to an evidenced route or exact scientific decision boundary.
managed_write_set:
- docs/tasks/FORGE_TRUST_CLOSURE_V1.md
- docs/reports/forge_trust_closure_v1/**
- docs/evidence/forge_trust_closure_v1/**
- tests/fixtures/forge_trust_closure_v1/**
- tests/test_forge_trust_closure_v1.py
- tests/test_factory_operational_store_readonly_schema_compat_v1.py
- tests/test_experiment_evidence_decision_v1.py
- tests/test_owner_lifecycle_projection_spine_v1.py
- tests/test_forge_research_flow_reliability_v1.py
- src/solana_alpha_lab/factory/operational_store.py
- src/solana_alpha_lab/factory/lifecycle_projection.py
- src/solana_alpha_lab/factory/document_runner.py
- src/solana_alpha_lab/factory/experiment_evidence.py
- src/solana_alpha_lab/factory/run_passport.py
- src/solana_alpha_lab/factory/workbench.py
- catalog/schemas/run_passport.schema.json
- docs/contracts/experiment_evidence_decision_v1.md
- docs/contracts/owner_lifecycle_projection_v1.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- catalog/assets/**
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
- STOP_REAL_DATA_HOLDOUT_PROVIDER_DEPLOY_SETTINGS_CREDENTIALS_MONEY
- STOP_NEW_SCIENTIFIC_PROTOCOL_ESTIMAND_OR_UNRESOLVED_MATERIAL_TRUTH_CONFLICT
- STOP_RESOURCE_ENVELOPE_WITH_RETAINED_INCOMPLETE_EVIDENCE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/experiment_evidence_decision_v1.md
    - delivery-harness/policies/solana-alpha-lab.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_trust_closure_v1/delivery_completion.json
    - docs/evidence/forge_trust_closure_v1/independent_review.json
    - docs/evidence/forge_trust_closure_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

# FORGE_TRUST_CLOSURE_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH, owner-supplied
FORGE_TRUST_CLOSURE_V1_PRD_SSD.md sha256
8c614c82e29969f5428ae498f47a28d22c7dc9c81d2aaafdc3d4445c73308215.
Explicit owner execution request authorizes bounded repair, related causal
defects, synthetic replay and routine Git delivery. Merge requires a separate
exact owner phrase after machine readiness; no inherited delegated phrase.

DECISION_DELTA: owner can trust implemented execution/current-read/guard/recovery
behavior in declared synthetic fidelity. Consumer: ordinary Forge operator,
ExperimentSpec dossier, Workbench and independent next executor.
UNCERTAINTY_REMOVED: BAA-001/002 causal repair and material original residuals;
BAA-003 exact scientific continuation gap rather than vague WATCH.
CAPABILITY_OR_EVIDENCE: source-owned repair, same-path replay, original 56-charter
denominator with obligation deltas, compact report/ledger and reproducible entry.
STOP: exact-head CI and merge-readiness, or a material authority/resource boundary.
NEXT: use requalified capability or the single exact BAA-003 decision delta.

Oracle: existing source contracts, independent SQLite mode=ro observation,
native committed producer records and fresh-process consumer readback. Cheapest
falsifiers: original WAL probe and standalone producer/bridge on pinned baseline,
then same routes on candidate, without inserted internal evidence relations.
Acceptance denominator: TC-01..TC-14 and original A01..F10 charter IDs from
audit head ea4afb52b9d188c378d2a9850ba1b26c85496821 (PR393 OPEN at entry).
Original audit bytes/verdicts remain immutable and are not accepted-main assets.
Residual obligations are mapped before expanded batches; historical PASS is
never a candidate PASS by mere copying. Scientific proxy is not NetReturn/OOS.

Resources: reuse existing locked runtime/image, offline product runs, owned
synthetic roots, 2 CPU/2 GiB/128 PIDs per container, <=2 GiB new evidence,
<=200 generated sequences; monitor each batch and keep failures/retries.
No new runtime downloads, dependency adoption, external model transport or paid
calls. Native critics are independent read-only review, not confined actors.
Actor tools require enforced isolation; otherwise retain precise UNVERIFIED.
REPLAN_TRIGGER: recurring boundary without new evidence, impossible falsifier,
preparatory-only output, second provider/route pivot, resource boundary.

Reuse: WRAP the pinned audit kit and existing runtime; BUILD only bounded
project-owned identity/reader repairs. CAPABILITY_RADAR_NOW=NONE.
PRODUCT_HORIZON_NOW: restore this implemented consumer loop.
PRODUCT_HORIZON_WATCH: chronological recipe successor, activated only by the
exact scientific/capability disposition proved in this atom.
