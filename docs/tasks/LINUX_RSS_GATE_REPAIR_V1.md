---
task_id: LINUX_RSS_GATE_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-08'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 20294a7677f14e93f8bb5dd6b4d339f2e15302d5
  expected_upstream: origin/main
  expected_upstream_oid: 20294a7677f14e93f8bb5dd6b4d339f2e15302d5
  expected_branch: codex/linux-rss-gate-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Diagnose the Linux memory child on the existing Actions runtime, repair only
  the proven RSS measurement or workload cause, retain the 512/768 MiB limits,
  and restore exact-head delivery evidence without repeating Forge science.
managed_write_set:
- docs/tasks/LINUX_RSS_GATE_REPAIR_V1.md
- src/solana_alpha_lab/factory/live_cohort_source_bundle.py
- tests/test_legacy_fat_open_bounded_artifacts_resume_v1.py
- tests/test_linux_rss_gate_v1.py
- scripts/prove_linux_rss_gate.py
- .github/workflows/ci.yml
- docs/evidence/linux_rss_gate_repair_v1/**
- docs/contracts/linux_rss_measurement_v1.md
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_FORGE_SCIENCE_LOOK_BUDGET_OR_NATIVE_BYTES_CHANGE
- STOP_RESOURCE_LIMIT_WEAKENING_SKIP_OR_MASK
- STOP_PRODUCTION_DATA_VPS_DEPLOY_SETTINGS_OR_PROVIDER_ACCESS
- STOP_NEW_DEPENDENCY_SERVICE_OR_EVALUATOR
- STOP_HISTORY_REWRITE
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [MODULE-LIVE-COHORT-SOURCE-BUNDLE-001]
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/linux_rss_measurement_v1.md]
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# LINUX_RSS_GATE_REPAIR_V1

Authority: direct owner EXECUTE instruction dated2026-10-08. PR384 is merged;
historical main CI37709815254 FAILURE and post-merge DENY remain immutable facts.
PR383 and subsequent Forge checks are separately sequenced work, not this atom.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: DESIGN_SPEC (one narrow measurement
contract). Route DIRECT_CODEX_DELIVERY, actor CODEX. MODEL_EFFORT: SOL_XHIGH.
Existing skill: delivery-harness, systematic-debugging, test-driven-development.
New tool/plugin/connector/dependency/automation: NONE. Reuse existing Actions
ubuntu24.04, pinned uv/Python3.13.14 and locked dependencies; no install adoption.
GitHub transport, draft diagnostic uploads and bounded Actions execution are
the routine Git/GitHub exception to external_caps, explicitly requested here.

DECISION_DELTA: allow resource gate recovery based on process-local evidence,
not a raised cap or a blind CI retry. UNCERTAINTY_REMOVED: whether the unchanged
worker exceeds512 MiB or only ru_maxrss carries pre-exec parent memory.
CAPABILITY_OR_EVIDENCE: authoritative current-image peak RSS, true-over-limit
adverse regression and durable GitHub proof. Consumers: existing memory-child
resource tests and source builder. No operator UI changes; no owner-UX review.

Cheapest falsifier: same baseline memory-child workload under small and600 MiB
resident parents on the existing Linux Actions runtime, recording VmHWM,
VmRSS, ru_maxrss before/after and original gate result. No workload replacement.
Before repair, upload diagnostic-only source on a preserved non-candidate
codex/linux-rss-gate-probe-v1 branch. Existing ci.yml manual dispatch gets a
strict probe-only mode; diagnostic success is NEVER exact PR/main acceptance.
The final candidate restores the original workflow bytes and retains Actions
links and producer SHA. This is one atom's diagnostic phase, not a new task or
an owner merge candidate. No merge claim or CI acceptance claim for that branch.
Final task-branch push requires full harness evidence/preflight and reviews.

DoD: Linux unchanged workload evidence; proven minimal owner fix; regression
rejects genuinely high child memory and distinguishes inherited parent memory;
512/768 MiB constants unchanged; affected consumers pass; isolated code/goal/
architecture reviews, Catalog propagation, PR exact-head CI and readiness.
H08/H09 source receipts, recipe, definition/look/accounting remain frozen.
STOP: material root-cause/contract decision or exact machine owner merge phrase.
NEXT: owner-approved guarded merge/readback, then separately PR383 review/merge.
REPLAN_TRIGGER: actual worker VmHWM over512 MiB requiring another existing
workload owner; proof cannot run; conflicting memory semantics; budget overrun.
Evidence budget: one before-repair diagnostic, one targeted final Linux proof,
affected tests only locally, one full exact-head PR CI per final fingerprint.
If actual local probe fails before the workload, fix the mechanical cause before
rerunning. Do not retry historical CI37709815254. No wide Forge audit.
PRODUCT_HORIZON_RADAR: NOW NONE; WATCH another current-image RSS consumer mismatch.
Rollback: an ordinary owner-gated revert restores the prior metric, preserving
all data/history. A missing/unreadable Linux HWM must fail safely, never zero-fill.
