---
task_id: OPPORTUNITY_EPISODES_PROTECTION_COMPLETENESS_RECONCILIATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6d8588fac51a8e95779e166a4f8e14f76a0cf115
  expected_upstream: origin/main
  expected_upstream_oid: 6d8588fac51a8e95779e166a4f8e14f76a0cf115
  expected_branch: codex/opportunity-episodes-protection-completeness-v1
  dirty_mode: ALLOW_REPORTED
objective: Reconcile source-owned current protection for native OPPORTUNITY_EPISODES exploratory fragments through existing plan and value-entry gates, preserving frozen history and preparing an exact metadata-only installation proposal without real values or activation.
managed_write_set:
- docs/tasks/OPPORTUNITY_EPISODES_PROTECTION_COMPLETENESS_RECONCILIATION_V1.md
- src/solana_alpha_lab/factory/episode_current_protection.py
- src/solana_alpha_lab/factory/opportunity_episodes.py
- src/solana_alpha_lab/factory/research_fragments.py
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/episode_required_outcomes.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- scripts/research_fragments.py
- configs/episode_current_protection_sources_v1.yaml
- docs/contracts/episode_native_required_outcomes_v1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/operator/RESEARCH_FRAGMENTS_V1.md
- docs/evidence/opportunity_episodes_protection_completeness_reconciliation_v1/**
- tests/test_research_fragments_v1.py
- tests/test_episode_native_required_outcome_contract_v1.py
- tests/test_hfic_list_aware_vertical_v1.py
- tests/test_forge_research_flow_reliability_v1.py
- tests/test_opportunity_episodes_vertical_v1.py
- tests/test_hfic_temporal_production_runner_v1.py
- tests/fixtures/episode_native_required_outcomes_v1/proof.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
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
- SOURCE_CLOSURE_OR_AUTHORITY_UNRESOLVED_BEFORE_MAIN_IMPLEMENTATION
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_CANONICAL_INSTALLATION_WITHOUT_EXACT_ROOT_PROPOSAL_AND_SEPARATE_OWNER_SCOPE
- NO_REAL_VALUES_MAIN_CRITIC_PLAN_ACTIVATION_ASSIGNMENT_OR_BUDGET_MUTATION
- NO_PRODUCER_SCOUT_RUNTIME_PROVIDER_DEPENDENCY_TRADING_OR_HISTORY_CHANGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/opportunity_episodes_jupiter_v1.md
    - docs/contracts/episode_native_required_outcomes_v1.md
    - docs/operator/RESEARCH_FRAGMENTS_V1.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# Current protection reconciliation

Direct owner EXECUTE of unified PRD+SSD dated 2026-10-19 authorizes this one
connected atom. The attachment is the approved requirement source, not independent
merge, installation, scientific or external authority. Its SHA256 is recorded in
local source evidence. No duplicate PRD, SSD, audit project, database or scheduler.

ENTRY: START_WITH_PATCH, subject to source closure below. SPEC_ROUTE: PRD_LITE
(the owner's unified design already exists). Route/actor DIRECT_CODEX_DELIVERY/CODEX.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH. CAPABILITY_RADAR_NOW: NONE.
ADOPT existing source owners, native protection_decision, ResearchStore writer,
release pins and fragment runner. WRAP only the current metadata assessment and
versioned publication missing from those owners. No new dependencies or providers.

DECISION_DELTA: an exploratory fragment can prepare and execute an authorized check
against genuinely current protection without manually renewing dates or rewriting
producer/release history. Named consumer RFV-8228C9408D18DE5CC98C9C1EA924B1C8;
other direct consumers are native discovery and Spec 1.4 fixed-time binding.
UNCERTAINTY_REMOVED: authority-source completeness, TASK-22 scope, current-versus-
frozen admission, late deny before values, idempotent restart/CAS and next-cohort
compatibility. CAPABILITY_OR_EVIDENCE: current status/preview/install -> existing
plan -> native due measurement -> cold saved readback on a controlled fixture.
STOP: one exact merge phrase after exact-head readiness, plus separately bound
metadata-only installation. Scientific plan apply remains a separate authority.
NEXT: operational current-proof install/readback on accepted code, then prospective
existing plan proposal. REPLAN_TRIGGER: missing authority, ambiguous source scope,
new current writer, repeated blocker, need for Scout/producer mutation or a new
scientific outcome. Do not build general infrastructure around unresolved authority.

## Pass 1 checkpoint and source closure

Baseline exact main 6d8588fac51a8e95779e166a4f8e14f76a0cf115; isolated task
worktree, original checkout unchanged. Harness check PASS; existing Git/gh access
verified (sandbox keyring failure resolved by read-only outside-sandbox check).
No due unresolved active time gate. Existing tools suffice; no installation needed.

Observed local metadata: canonical root identity
6ba8e087ac18c9edbb5c9216207cef47459ae534d1e6abee80db23cce3478812,
426 ResearchEvents; Fast Lane root identity
46b121424a2ec4d0eeb3fa32521ce50b7316c01a7a461623f091d98657779ba4,
7 events. Record counts alone establish no absence of assignments. Their native
record schemas, declarations and experiment policies require interpretation.

TASK-22 owner resolution: accepted A6 receipt binds split v2
973a9ff6dd2a376e62dee9289a57cbb62f06c8efb5a619fa6b7b2a7914dd0683,
ledger v2 2282e5d1eac09a0ce940a5700f04b03ff4d75fc9cd4d65e08e5fe7deda88ca51
and consumer profile 71a253d8b94f32a954d0195d2d544fdfb94e1b41ae680313bb48caa115ed01a0.
Assignment T22-HOLDOUT-ASSIGNMENT-001 protects T21-R3, UNTOUCHED/DENY, inside
TASK-21 dataset aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae.
Its August selection/label interval is distinct from October OPPORTUNITY_EPISODES;
this is not a global mint ban or permission to open TASK-22. v1 is historical.
Consumption registry records=[] records consumption only, never reservation absence.

List A protocol is DESIGN_VALIDATED_BOUND_CONTRACT_NOT_READY, sample UNBOUND;
future_execution_contract value_read_authorized=false, activation_authorized=false.
This is no confirmatory grant. Existing episode labels are EXPLORATORY_REUSE,
holdout=false, confirmatory_reuse_forbidden=true. All four immutable releases pin
BOOTSTRAP-EXPLORATORY-REUSE-INVENTORY-20261006 semantic SHA
f70a7f2d82b27bd39b1affbb72be339401bb0d223275965ce68df795112ec3ef.
Frozen parser currently returns ALLOW for this limited-as-of document without
current binding: the cheapest metadata-only reproducer confirms the defect.

Remote read-only delta: producer observation_rdp/protection/assignments has one
known bootstrap, entries=0, raw SHA
4fbfa346b2875eac3e694e7edf0faa3a7daeec7ca46776217ec75fa57b866918.
Producer observation_rdp research manifests now exist; producer data_plane and
fast_lane_research_data_plane do not. A copied remote file cannot prove the
absence of future changes by a mutable remote current-authority writer.

Scout seam only: pinned native source 88763e400e5dac7462e70275b23b74e061410445,
metadata() -> resolve_published_episode_binding; inventory() copies *.json native
assignments and immutable release dependencies. No Scout writes/search/run. A
backward-readable assignment envelope is required; compatibility never establishes
new-rule enforcement by this older pin.

SOURCE_CLOSURE_STATUS: CLOSED_SCOPED, independently challenged before implementation.
The exact owner PRD SHA256 is
89503bb3a3d7ef2911fee1df748dbba81c0b0faa3f2f3473f8b6472dd5c27d45.
PRD 5.1/5.3/7.1 explicitly authorize the small source-role mapping. Existing
contract 10 fixes producer pins as admission-only; current native namespace is
already protection/assignments in the passed local root. No competing concrete
producer current-authority binding exists. Do not invent an approval for a
hypothetical future writer. Both ResearchStores, local assignment namespace,
accepted TASK-22 v2, consumption registry, existing experiment policies and List A
protocol are the scoped current inputs. Producer/release pins and input labels
remain separate mandatory per-input dependencies. New unknown authoritative
links/versions return UNRESOLVED. Advisory holdouts_not_touched copies do not
create reservations; their referenced scope remains UNKNOWN, not asserted empty.
Actual empty/nonempty is determined by the source assessment, not this closure.
Source-specific projection excludes checks/logs/generated/current proof outputs.
All supported source changes are interpreted again before admission; unknown
policy text, assignments, roles or links cannot be silently re-hashed into ALLOW.
Local source read lease is ResearchStore manifest-last plus native writer lease;
multiple roots use a revalidated vector, not a claimed distributed transaction.

Independent pass-1 critic: source_authority_critic, CLOSED_SCOPED, fresh context.
Baseline targeted fragment suite: 2 tests PASS in 344.120s. Real metadata-only
plan-preview succeeds through source/root/universe/capability shape and reports
HOLDOUT_UNRESOLVED; no neighboring defect observed. Seed remains registered,
result SHA unchanged, plan disabled, inventory before/after
56663b87d35c7f4597243c2d61f37dc99a6a79533dbc7dfc32ea5177bd7ea684.

Candidate technical path if closure resolves: one pure frozen parser retained,
one neighboring current IO/assessment owner; existing native assignment envelope
with additive source-set metadata, immutable receipt before CAS pointer outside
assignment glob. Current resolver revalidates source-specific projection on each
new action, does not key freshness on date or whole-store inventory, and never
writes from GET. Normal compatible cohorts verify their frozen deps independently.
Mandatory sources use explicit native interpretation versions; missing/unknown
owner is scoped UNRESOLVED, not entries=[].

## Pass 2 and verification (conditional on closure)

- [x] Freeze exact source set and native interpretation versions. Actual read-only assessment: scoped complete-empty; current installation remains absent. Advisory scope UNKNOWN and confirmatory restrictions remain explicit.
- [x] Implement assessment/current resolver and metadata-only preview/apply/CAS.
- [x] Route fragment plan/writer/last loader, fixed-time verifier and discovery
      through that resolver; preserve historical release/import and saved reads.
- [ ] Extend existing controlled fixture for A-G: stale pin, proven empty, next
      cohort/day, relevant/ambiguous scope, late deny, unavailable/changed source,
      crash/retry/reservation and direct consumers. Unsafe paths have loader sentinel.
- [ ] Real read-only seed/source readback and proposal outside canonical root;
      no real outcomes/replay/plan enable. Verify next plan's neighboring gates.
- [ ] Finish impacted operator/contracts and native Catalog propagation; isolated
      code, goal/DoD, architecture and owner-UX reviews on exact final diff.
- [ ] Bind evidence, preflight-push, ordinary PR, exact-head CI and readiness;
      one handback with phrase and separately bound operational install proposal.

Engineering, operational installation, monitoring enabled and new evidence observed
are distinct. Historical seed/result/MAIN, assignments, producer schedule pins,
market identity/spend and typed UNKNOWN remain intact. Reverting cannot restore a
permissive parser as current authority. Disable dependent plan if rollback needed,
retain restrictions and receipts. No canonical data-plane cleanup or copies.


Pass-2 implementation checkpoint: one neighboring IO owner over the unchanged pure
frozen parser; source-specific projection, strict native versions, accepted TASK-22
v2/source/time boundaries and explicit advisory UNKNOWN. Real metadata-only preview
is scoped complete-empty; canonical current status remains NOT_INSTALLED. No real
installation, plan activation, new market look or original scientific mutation.
Current context is re-read through fresh committed ResearchStore metadata, including
inside cached display packets. Pointer publication uses the native immutable writer
and existing writer lease; partial receipts are inactive and retries idempotent.
Late native protection revalidation occurs after reservation and before values.
Old Scout pin 88763e400e5dac7462e70275b23b74e061410445 reads the new assignment
1.0 envelope without schema failure; it does not enforce the new current contract.
Local integration attempts during edits correctly refused GIT_MUTATION_DETECTED /
PREFLIGHT_GIT_COMPOSITE_MISMATCH. Freeze candidate content before the next native
preflight/test run; no source/authority weakening or scientific retry follows.


Bounded review replan, same outcome/write set: replace spelling-specific last-loader
checks with one native artifact-kind boundary, and classify supported native
ResearchEvent envelope owners/forms instead of ignoring opaque version-1 payloads.
Contradictory identities and relabelled episode Parquet refuse before values;
unknown producer/form/packet version returns typed UNRESOLVED. No generic recursive
assignment evaluator, registry of new reservations or additional scientific scope.
The c20bc537 committed vertical passed 9 tests in 506.806s; Spec 1.4 direct consumers
passed, with two existing campaign-specific skips. Three-process restore's missing
root-bound setup is repaired before its ordinary preflight (original oracles kept).
New metadata/sentinel checks and exact-head CI must validate the strengthened final
candidate. No full local gate; guarded merge remains its sole executor.
