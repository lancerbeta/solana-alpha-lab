---
task_id: FORGE_RELIABILITY_AUDIT_CONTINUATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-08'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0dbe4d4bb5ce9703332a0620987a47eac05c4cdc
  expected_upstream: origin/main
  expected_upstream_oid: 0dbe4d4bb5ce9703332a0620987a47eac05c4cdc
  expected_branch: codex/forge-reliability-audit-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Complete the bounded offline continuation of the existing Forge reliability
  audit through K1-K6, preserving original O01-O12/P01-P08/R1-R8/J1-J5
  denominators, raw failures and scientific authority; deliver one remotely
  readable evidence PR and at most one connected repair of a reproduced
  material defect in an existing owner and its direct consumers.
managed_write_set:
- docs/tasks/FORGE_RELIABILITY_AUDIT_CONTINUATION_V1.md
- docs/contracts/forge_reliability_audit_continuation_v1.md
- docs/reports/forge_reliability_audit_continuation_v1/**
- docs/evidence/forge_reliability_audit_continuation_v1/**
- tests/test_forge_reliability_audit_continuation_v1.py
- tests/test_ci.py
- scripts/validate_ci.py
- scripts/render_ci_workflow.py
- .github/workflows/ci.yml
- tests/fixtures/forge_reliability_audit_continuation_v1/**
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- docs/contracts/forge_research_policy_runtime_v1.md
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
- STOP_NEW_EXACT_OWNER_MERGE_PHRASE_AFTER_CI_AND_READINESS
- STOP_LIVE_VPS_REAL_RESEARCH_HOLDOUT_PROVIDER_CREDENTIAL_DEPLOY_MONEY
- STOP_SECOND_INDEPENDENT_REPAIR_OR_NEW_CAPABILITY
- STOP_NATIVE_RESEARCH_OUTPUTS_OVER_4
- STOP_DEFAULT_OR_RSS_LIMIT_INCREASE_SCIENTIFIC_SEMANTICS_CHANGE
- STOP_MATERIAL_AUTHORITY_OR_TRUTH_CONFLICT
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-TEMPORAL-DISCOVERY-001, MODULE-HFIC-PREFLIGHT-ADMISSION-001, CONFIG-EXPERIMENT-CAPABILITY-REGISTRY-V2-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/forge_grounded_handoff_closure_v1.md
    - docs/contracts/forge_research_policy_runtime_v1.md
    - docs/contracts/forge_list_aware_research_scope_v1.md
    - docs/contracts/experiment_evidence_decision_v1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_reliability_audit_continuation_v1/delivery_completion.json
    - docs/evidence/forge_reliability_audit_continuation_v1/independent_review.json
    - docs/evidence/forge_reliability_audit_continuation_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

# FORGE_RELIABILITY_AUDIT_CONTINUATION_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: PRD_LITE (this contract and
the owner attachment). MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
Authority: owner's explicit `сделай согласно вложению`, attachment
`SMIAL_FORGE_AUDIT_CONTINUATION_V1_CODEX.md`, Task ID as above.

DECISION_DELTA: owner can distinguish supported ordinary offline research,
safe refusals, unproved positive endpoints and repairs actually required.
UNCERTAINTY_REMOVED: lifecycle, prior/evidence identity, cumulative budgets,
prefix semantics, recovery/cost and chronological-consumer limits on AUDIT_SHA.
CAPABILITY_OR_EVIDENCE: six probes and original outcome/risk/journey ledger,
with independent native scientific Critic and independent evidence review.
STOP: exact merge gate, completed bounded evidence, or stated material boundary.
NEXT: at most one product recommendation derived from evidence.
REPLAN_TRIGGER: repeated same-boundary failure after repair, a second independent
repair, impossible cheapest falsifier, or four native research outputs consumed.

Named consumer: owner and independent Project Chat validator. User-visible
result: one compact Russian verdict and one task PR/evidence index.
Cheapest falsifier: registry/public runner supports only frozen same-input
temporal replay, with no accepted frozen-later-cohort consumer.

Evidence budget: existing locked CPython 3.13.14 and dependencies; disposable
synthetic stores, existing production producers, no full local gate before PR,
one meaningful fallback per technical blocker, native research outputs <=4
(engineering evidence reviewers separate). Numerical comparisons and assertions
are frozen before values in `docs/reports/forge_reliability_audit_continuation_v1/PROBE_PLAN.md`.

Source is initially unchanged. Reproduced material defects require preserved
RED/impact/root cause and an explicit contract/write-set update before the one
connected repair. No implicit authority for a second repair. GitHub routine
read/commit/non-force task-branch push/one PR/CI is separately authorized by the
attachment. Product network, credentials and real data are forbidden.

Isolation: independent clone/common Git directory. Native lifecycle source and
refs are frozen from preflight through terminal; raw outputs and instrumentation
stay outside it. Delivery begins after that lifecycle closes.

Prior proof inheritance requires available actual results and unchanged relevant
owners; historical status prose and test counts grant no inheritance. BASE and
POST_REPAIR findings remain separate. No alpha, OOS confirmation, scientific
acceptance, strategy readiness or live health claim.

Entry capability radar: NOW=NONE; existing Git/gh, locked runtime, Harness,
Forge/independent-Critic protocol and native isolated reviewers suffice.
Product horizon: NOW=NONE pending probes; WATCH=chronological consumer only
after an evidenced gap and separate exact scientific/product authority.

## Connected repair authorized after BASE evidence

RED: collision-base.json records 2/2 attempts in which three distinct frozen
PREVIEW descriptors with the same landed payload consume only one of two slots.
Both journal occupancy and operation allowance deduplicate payload bytes instead
of chargeable request identity. Repair only these consumers in the existing
ordinary-operation owner; keep reservation/landing lineage, immutable history,
legacy unkeyed previews and shipped limits. No second repair: confounders shape
incompatibility and chronological-consumer absence remain separate findings.
OWNER_UX_CRITIC is added for changed occupancy/readout semantics. Catalog writes
are generated propagation only. The final user steering forbids a permanent
audit harness and large logs in Git; retain a minimal reproducer and key evidence.

## Owner-authorized delivery allowance after CI timeout

The owner explicitly authorized a one-off generous CI timeout and delegated
substitution of the machine-rendered merge phrase after green exact-head CI and
merge-readiness. This supplements the original merge stop; it does not bypass
readiness, failed evidence, guarded merge or post-merge readback.

CI run 37784967070, attempt 1, exact head
341768770e20e0495b310d4f9467f12037060dab: shard 4 was cancelled after 30 minutes;
GitHub annotation: `The job has exceeded the maximum execution time of 30m0s`.
All other executed jobs passed. Preserve this failed attempt in Actions.
Authorize only an exact workflow/validator timeout expression: PR 386,
pull_request event, shard 4 receives 60 minutes. Every other event, PR and shard
retains 30 minutes. This is a delivery allowance, not a second product repair;
PREVIEW remains the sole product repair. Tests, aggregator, pins, commands,
scientific/default/RSS limits, owner gate and profile bindings are unchanged.
