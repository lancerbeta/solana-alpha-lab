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
- docs/evidence/linux_rss_gate_repair_v1/**
- docs/contracts/linux_rss_measurement_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
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
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/linux_rss_measurement_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/linux_rss_gate_repair_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/linux_rss_gate_repair_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/linux_rss_gate_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LINUX_RSS_GATE_REPAIR_V1

Authority: direct owner EXECUTE instruction dated2026-10-08. PR384 is merged;
historical main CI37709815254 FAILURE and post-merge DENY remain immutable facts.
PR383 and subsequent Forge checks are separately sequenced work, not this atom.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: DESIGN_SPEC (one narrow measurement
contract). Route DIRECT_CODEX_DELIVERY, actor CODEX. MODEL_EFFORT: SOL_XHIGH.
Entry tools: existing harness/debugging/TDD skills and pinned Linux Actions;
new dependency/plugin/service/automation NONE. Routine GitHub transport and
bounded diagnostic upload/execution are explicitly authorized external exceptions.
DECISION_DELTA: restore a truthful memory gate. UNCERTAINTY_REMOVED: inherited
pre-exec ru_maxrss versus actual worker HWM. CAPABILITY_OR_EVIDENCE: current-image
RSS and a real released-memory overshoot regression for existing resource tests.
Cheapest falsifier: unchanged workload under0/600 MiB parents. Before-repair
Actions37714107620 reproduced the false failure; after-repair37714704552 passed
24 targeted cases, including an actual child peak over512 MiB being rejected.
The preserved codex/linux-rss-gate-probe-v1 branch is diagnostic-only, never a
merge candidate. Its temporary workflow/script are absent from the final diff;
main/PR full CI retain original bytes. No historical failed CI retry or relabel.
DoD: minimal owner fix, unchanged512/768 MiB limits, affected regression, three
isolated reviews, generated propagation, exact-head PR CI/readiness/readback.
H08/H09 and all science/data/accounting stay frozen; owner UI unchanged.
Additional direct owner authorization: "мержи сам, после получения мерж фразы,
разрешаю". After successful exact-head readiness renders the exact phrase, this
bounded repair may guarded-merge autonomously; record this conditional grant
truthfully, never claim the owner pasted a future hash-bound phrase.
STOP: material boundary or machine DENY; fix routine causes within this scope.
NEXT: safe merge/readback; PR383 remains separate. REPLAN_TRIGGER: actual worker
over512 MiB needing another owner or materially conflicting resource semantics.
Budget: one before/one after targeted Linux proof; affected local tests; final
full CI once per fingerprint. PRODUCT_HORIZON_RADAR: NOW NONE, WATCH NONE.
Rollback: ordinary authorized revert, immutable source/history; no zero-filled RSS.
