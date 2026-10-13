---
task_id: SMIAL_MANAGED_COLLECTION_I1_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-13'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 339c50dabe128a4c672028141f93d214152b6252
  expected_upstream: origin/main
  expected_upstream_oid: 339c50dabe128a4c672028141f93d214152b6252
  expected_branch: codex/smial-managed-collection-i1-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair the existing Opportunity Episodes owner delivery path with capture-scoped source versions, preserve C1 and historical packet replay, prove isolated exact C2 consume/repeat/recovery and integrity refusal, and prepare one gated OPERATE packet without production import or collector changes.
managed_write_set:
- docs/tasks/SMIAL_MANAGED_COLLECTION_I1_V1.md
- docs/evidence/smial_managed_collection_i1_v1/**
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- src/solana_alpha_lab/factory/live_cohort_vanilla_path.py
- src/solana_alpha_lab/factory/opportunity_episode_release.py
- scripts/discovery_evidence_release.py
- scripts/prove_managed_collection_i1.py
- tests/test_opportunity_episodes_vertical_v1.py
- tests/test_live_cohort_vanilla_owner_path_v1.py
- tests/test_opportunity_episodes_harness_v1.py
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
- STOP_MATERIAL_SCOPE_SAFETY_OR_TRUTH_CONFLICT
- STOP_PRODUCTION_IMPORT_DEPLOY_OR_EXTERNAL_WRITE_BEFORE_SEPARATE_EXACT_OPERATE_GATE
- STOP_COLLECTOR_GRANT_FROZEN_SCHEDULE_BACKUP_LEGACY_POLICY_RENEWAL_OR_SCIENCE_CHANGE
- REPLAN_REPEATED_SEAM_FAILURE_IMPOSSIBLE_FALSIFIER_SECOND_ROUTE_PIVOT_OR_BUDGET_BREACH
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/smial_managed_collection_i1_v1/completion.json
    - docs/evidence/smial_managed_collection_i1_v1/independent-review.json
    - docs/evidence/smial_managed_collection_i1_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# SMIAL_MANAGED_COLLECTION_I1_V1

Owner EXECUTE selects only I1 of SMIAL_MANAGED_COLLECTION_OPERABILITY_V1,
from the accepted 2026-10-13 PRD/SSD, sections 0-4 and 9-13. The source
document is preserved at `docs/evidence/smial_managed_collection_i1_v1/source-contract.md`.
Its exact SHA256 is `6f3cce30bbea09eeffe286ccb6f9bc3a53dddf46b213dae038be0dc4ab4880e3`.
I2-I5 are compatibility context only. The owner explicitly preserves the
working collector, its grant and frozen schedule. No blanket overwrite of
shared metadata, manual mirror repair, second importer or framework.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH (accepted source PRD/SSD).
Route/actor: DIRECT_CODEX_DELIVERY/CODEX. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: ordinary delivery can preserve both old and growing captures.
UNCERTAINTY_REMOVED: mutable unit identity, race, exact replay and cold recovery.
CAPABILITY_OR_EVIDENCE: capture-scoped views, producer-frozen metadata, genuine
conflict refusal, historical compatibility, real C1/C2 isolated oracle.
Named consumer: the existing `unpack-next-live-cohort` operator and a fresh agent.
Cheapest falsifier: exact C2 packet against C1 mirror returns one conflict;
the repaired public path must import C2 in a disposable copy, retain C1,
repeat C2 with no epoch bump and replay old C1 after a later capture.
STOP: exact merge gate or material blocker. NEXT: separately approved OPERATE
C2 consume, section 12 handback, tactical review before any next iteration.
REPLAN_TRIGGER: repeated seam failure, impossible oracle, second provider/route
pivot, material resource risk or budget breach. Evidence budget: focused existing
fixtures plus one isolated real replay (~34 MB source), bounded subprocesses,
compact metrics; no provider requests or pre-PR full local suite.

Frozen runtime locators: `local/canary_exit_and_100_per_day_arm_v1/20261013_resume/EXACT_RESUME_POINT.json`
and `c2-stop-receipt.json`. C2 is REL-20261008T000000Z-20261009T000000Z.
The resume file's prefix-overwrite proposal is superseded by accepted section 4.
Protect ACT-4744D4017AC4B196 and all existing ACT-2BFB07B6862365DF dependencies.

Oracle: C1 24 episodes/3336 pairs, C2 23/3197, total 47/6533. Preserve exact
episode/point membership, missing states, C1 release and original dataset bytes.
The aggregate lineage may add C2 only in the disposable copy, preserving C1's
entry. Canonical production C1 pins remain unchanged before OPERATE.
Exercise source mutation between manifest/transfer, changed publication/anchor,
unsafe paths/symlinks, partial transfer/resume and independently read releases.
No manual JSON reconstruction of historical source versions; absent exact bytes
must fail with a typed missing-version reason.

Tool Entry: existing delivery-harness, Git/gh, locked Python, native filesystem.
New plugin/connector/MCP/automation/package/service: NONE.
Factory Fit: FULL_REVIEW. NOW: I1 delivery seam. WATCH: continuity review due
2026-10-14T00:00:00Z (03:00 Moscow); no schedule or grant authority follows.
All active Git time gates are resolved/superseded. Remote readback is authorized
read-only inspection only; it grants no runtime mutation or credential change.

DoD before merge: actual original falsifier; risk-focused regression/oracle;
owning contract/CLI/runbook/Catalog propagation; isolated critics with the frozen
four-role plan; bound evidence; exact-head CI/readiness; one prepared OPERATE
packet with independent copy, exact target, rollback and numerical acceptance.
Runtime outcome remains CODE_READY_RUNTIME_PENDING until authorized C2 consume,
exact repeat, fresh-process cold check and existing recovery coverage.
