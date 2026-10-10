---
task_id: BIG_AGENTIC_AUDIT_V1
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
  expected_branch: codex/big-agentic-audit-v1
  dirty_mode: ALLOW_REPORTED
objective: Execute the owner-authorized bounded synthetic audit from Forge-ready consumption to science-to-strategy consumer acceptance; preserve real transitions, independent readback, reproducible findings and one NOW repair without product fixes.
managed_write_set:
  - docs/tasks/BIG_AGENTIC_AUDIT_V1.md
  - docs/reports/big_agentic_audit_v1/**
  - docs/evidence/big_agentic_audit_v1/**
  - tests/fixtures/big_agentic_audit_v1/**
  - tests/test_big_agentic_audit_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - STOP_PRODUCT_REPAIR_OR_SCIENTIFIC_SEMANTICS_CHANGE
  - STOP_UNPROVEN_CONTAINMENT_OR_REAL_DATA_SECRET_HOLDOUT_ACCESS
  - STOP_PROVIDER_DEPLOY_MONEY_OR_EXTERNAL_ACTION
  - STOP_NEW_DEPENDENCY_OR_UNAPPROVED_BOOTSTRAP
  - STOP_EXACT_HEAD_CI_AND_MERGE_READINESS_BEFORE_OWNER_PHRASE
context_requirements:
  catalog_asset_ids:
    - DOC-HYPOTHESIS-FORGE-OPERATOR-001
    - MODULE-FACTORY-V1-RESEARCH-STORE-001
    - DOC-EXPERIMENT-EVIDENCE-DECISION-001
    - DOC-SCIENCE-TO-STRATEGY-HANDOFF-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/contracts/forge_native_lifecycle_closure_v1.md
      - docs/contracts/forge_ordinary_operation_lifecycle_v1.md
      - docs/contracts/experiment_evidence_decision_v1.md
      - docs/contracts/science_to_strategy_handoff_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/big_agentic_audit_v1/completion.json
      - docs/evidence/big_agentic_audit_v1/independent-review.json
      - docs/evidence/big_agentic_audit_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

Owner authority: the explicit request to execute BIG_AGENTIC_AUDIT_V1, followed
by pause and explicit resume on 2026-10-10. Attachment SHA256:
cae0400ae48b79bec7c980c260c121a390363d3fd566f285aa86ab2c58524ace.
The attachment is the accepted audit specification, not product/science authority.
The research base d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc is provenance only.
The incoming FORGE_NATIVE_LIFECYCLE_CLOSURE_V1 is included in the frozen base above.

ENTRY_DECISION: START_WITH_PATCH (current Git binding and available Docker).
SPEC_ROUTE: BOTH, satisfied by the existing owner PRD+SSD; no second PRD.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: distinguish actual connected paths, honest stops, missing links
and one evidence-backed repair. UNCERTAINTY_REMOVED: bounded observations of
PIT, identity, budget, lifecycle, evidence joins and strategy handoff.
CAPABILITY_OR_EVIDENCE: replayable audit kit, complete 56-charter denominator,
traces/readbacks, deduplicated findings and Russian owner report.
Named consumers: owner, next repair executor, independent engineering reviewers.
Cheapest falsifier: exercise a coherent ordinary synthetic look, durable terminal,
actual experiment runner and existing strategy consumer; expose the earliest
missing producer instead of injecting its output.

Budget envelope: existing pinned CPython 3.13.14, uv 0.11.29 and uv.lock;
Docker bootstrap from official pinned images and locked dependencies explicitly
approved by owner in this chat. Bootstrap network is separate from audit runs.
No new dependency, provider, account, payment or scientific grant. Product tests
are offline, unprivileged, read-only source, 2 CPUs, 2 GiB RAM, 128 PIDs;
120 minutes product-run wall envelope, <=2 GiB retained synthetic evidence,
<=200 generated sequences, zero external model/API calls. Native actor lane
only if tools are demonstrably confined to that container; otherwise BLOCKED.
The ordinary Git branch/commit/non-force push/PR/CI transport is harness routine
authority, separate from product external_caps. Never merge without the exact gate.

STOP: bounded handback or a material boundary; NEXT: one recommended repair only.
Checkpoint disposition: PARTIAL_BLOCKED is permitted by the accepted spec;
audit kit delivery does not close the full audit/science DoD or mark canonical DONE.
REPLAN_TRIGGER: inability to prove isolation, same harness blocker after one
prescribed repair, budget breach, product fix or a second environment pivot.
Product defects are findings; no source-owner repairs are authorized.
Fixtures may enter downstream seams only as SEGMENT_PRODUCT_PATH/CONTRACT_ONLY,
with skipped producers explicit. Scripted Critic output is external transport
fixture and never independent live-agent evidence or scientific acceptance.

Entry capability radar: existing Docker, Git/gh, unittest, serializers/stores
and Harness; no new plugin/skill/service/connector. Reuse decision: WRAP existing
product-path tests and add narrow audit-only observers/reproducers.
Production tree, stores, holds, providers, settings and secrets stay outside all
audit mounts. Cleanup is limited to labeled owned containers and audit paths.
