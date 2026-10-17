---
task_id: I4_UNATTENDED_OPERABILITY_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-10-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 33b19d9cafde0039233e1f1d25de8d36d17e3687
  expected_upstream: origin/main
  expected_upstream_oid: 33b19d9cafde0039233e1f1d25de8d36d17e3687
  expected_branch: claude/i4-unattended-operability-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  The producer keeps collecting without the workstation, protects every future
  mature episode cohort as one independently restorable offhost closure, reports
  the managed bridge truthfully instead of asking for a manual successor, and
  leaves no orphaned heavy artifacts; the external host-loss receiver is a
  prepared owner-access step, not a code change.
managed_write_set:
  - docs/tasks/I4_UNATTENDED_OPERABILITY_CLOSURE_V1.md
  - docs/evidence/i4_unattended_operability_closure_v1/**
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/hot90_closed_day_loop.py
  - tests/test_managed_collection_release_seam_v1.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - catalog/assets/**
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/generated/**
  - docs/PROJECT_MAP.md
  - docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
  - STOP_DEPLOY_RECEIVER_TIMER_OR_DRIVE_WRITE_BEFORE_EXACT_OPERATE_APPROVAL
  - STOP_SCIENCE_QUOTA_PROVIDER_RETENTION_OR_PHYSICAL_RECLAIM_CHANGE
  - REPLAN_IF_A_NEW_SUBSYSTEM_SCHEDULER_OR_BACKUP_ENGINE_IS_NEEDED
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
      - docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/i4_unattended_operability_closure_v1/completion.json
      - docs/evidence/i4_unattended_operability_closure_v1/independent-review.json
      - docs/evidence/i4_unattended_operability_closure_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# I4_UNATTENDED_OPERABILITY_CLOSURE_V1

Owner EXECUTE (17.10.2026) of the single PRD+SSD
`SMIAL_I4_Operability_Closure_PRD_SSD_V1_2026-10-17.md` (owner-supplied; this
contract is the durable brief, no separate spec/plan). Parent:
`SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`. ENTRY_DECISION: START_AS_WRITTEN.
MODEL_EFFORT: SOL_XHIGH. SPEC_ROUTE: NONE. Factory Fit: FULL_REVIEW.
Reuse: WRAP the existing closed-day loop, native episode capture and the
existing `unpack-next-live-cohort` consumer; no new store, scheduler, CLI or
backup engine.

## Findings that shaped the change (read-only, 17.10)

- Managed lineage `0849fa83…` RUN, grant VALID, `protected_bridge` = B
  `ACT-A26CF9B0815A36F2`, `bootstrap_not_before` = B `stops_admitting_at`
  (18Oct00:00Z). The operability packet recognised only activations with
  `payload.managed_collection`, so B got `CAMPAIGN_SUCCESSOR_REQUIRED`.
- Day archives 13–16 Oct (downloaded from Drive) matched 6,913 of C3's 7,414
  closure entries by sha256 (0 mismatches). Missing: the cohort export (closure
  receipt, frames, schedule, protection, frozen `capture_metadata`) and 488
  completed publication jobs, plus 6 objects of the still-open day 17. The
  export exists only when the workstation runs capture over SSH.

## Outcome

- DECISION_DELTA: the workstation is no longer required to protect a cohort.
- UNCERTAINTY_REMOVED: whether ordinary producer durability already covers a
  cohort closure (it does not: export + jobs were absent).
- CAPABILITY_OR_EVIDENCE: (1) exact protected-bridge recognition in
  `_managed_continuation_state` (verified profile, exact bridge identity,
  bootstrap not after the bridge boundary); (2) the closed-day run protects up
  to two mature unprotected cohorts per run as `COHORT_CLOSURE_<sha>.zip` with
  receipts; (3) runbook for the detached consumer and owned-output disposition.
- STOP: exact-head CI plus `ready_for_owner_phrase=true`; deploy, receiver,
  canary scheduling and cleanup follow one staged OPERATE packet.
- NEXT: ordinary Forge run; this task does not continue storage work.
- REPLAN_TRIGGER: dedup/reference packaging, schema change or a second importer
  becomes necessary.

## Acceptance

1. Synthetic production path (existing release seam): B bridge before the
   bootstrap is `MANAGED_CONTINUATION`; another activation or a bridge ending
   before the bootstrap is not. Four managed days across a Monday-UTC boundary
   with one failing child; the production closure step protects every mature
   cohort (default boundary first), repeats with zero uploads and leaves no
   staging; a consumer holding only the offhost objects seals/imports all five
   cohorts and reads the Forge preflight.
2. Real producer working-path probe: selection → native capture → packaging of
   C3 (7,414 files, every sha256 checked) in a temp root with Drive refused.
3. Live (OPERATE): first producer-made closure readback and detached import;
   managed transitions 18 and 19 Oct; external receiver DOWN/RECOVERED.

Non-goals: physical reclaim, retention/RPO change, 100/day increase, science,
provider calls, rewrite of #412 receipts or historical results.
Rollback: revert the reader/loop change; receipts and Drive objects are
append-only and stay valid.
