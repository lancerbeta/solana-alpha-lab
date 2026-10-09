---
task_id: FORGE_EVIDENCE_GUIDED_GENERATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-09'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0f89ffd8018c05fbafaf79ef609c7dadf888807f
  expected_upstream: origin/main
  expected_upstream_oid: 0f89ffd8018c05fbafaf79ef609c7dadf888807f
  expected_branch: codex/forge-evidence-guided-generation-v1
  dirty_mode: ALLOW_REPORTED
objective: Add phase-admissible evidence-guided context and bounded source-bound research working memory to ordinary Forge, independently retaining full-scope safety guards, proving R1-R10 and P1-P8 with production-path synthetic and isolated native evidence.
managed_write_set:
- docs/tasks/FORGE_EVIDENCE_GUIDED_GENERATION_V1.md
- docs/contracts/forge_evidence_guided_generation_v1.md
- docs/evidence/forge_evidence_guided_generation_v1/**
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/forge_input_receipt.py
- src/solana_alpha_lab/factory/hfic_prior_memory.py
- src/solana_alpha_lab/factory/hfic_generation_context.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/hfic_memory_policy.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/prior_work.py
- src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
- scripts/hypothesis_forge.py
- configs/hypothesis_forge_independent_critic_v1.yaml
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_forge_evidence_guided_generation_v1.py
- tests/fixtures/forge_evidence_guided_generation_v1/**
- tests/test_hfic_preflight.py
- tests/test_hfic_session.py
- tests/test_hfic_cli.py
- tests/test_hfic_critic_prior_memory_closure_v1.py
- tests/test_hfic_forge_prior_context_capacity_repair_v1.py
- tests/test_forge_research_flow_reliability_v1.py
- tests/test_hypothesis_forge_independent_critic_v1.py
- tests/test_hfic_operational_closure_v1.py
- tests/test_hfic_list_aware_vertical_v1.py
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
- STOP_LIVE_RDP_HOLDOUT_PROVIDER_DEPLOY_CREDENTIALS_MONEY
- STOP_NEW_DEPENDENCY_SUBSYSTEM_SCIENTIFIC_POLICY_BUDGET_OR_OPERATOR
- STOP_REPEATED_SEAM_FAILURE_MATERIAL_TRUTH_CONFLICT_OR_NATIVE_CAP_28
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/forge_research_flow_reliability_v1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_evidence_guided_generation_v1/completion.json
    - docs/evidence/forge_evidence_guided_generation_v1/independent-review.json
    - docs/evidence/forge_evidence_guided_generation_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# FORGE_EVIDENCE_GUIDED_GENERATION_V1

Authority: owner explicitly requested execution of the attached
SMIAL_Evidence_Guided_Generator_PRD_SSD_V1_2026-10-09.md. Its R1-R10,
P0 invariants, P1-P8 and section14 acceptance remain the denominator.
ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH. Route/actor:
DIRECT_CODEX_DELIVERY/CODEX. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.

DECISION_DELTA: ordinary generators and independent Critics receive a bounded,
phase-admissible working view with provenance and useful prior failure meaning.
UNCERTAINTY_REMOVED: archive capacity, mandatory evidence selection, memory
meaning and formulation quality on fixed synthetic cases.
CAPABILITY_OR_EVIDENCE: reusable context/detail contract plus production-path
machine/native comparison, with separate implementation/safety/formulation/
comparison/delivery verdicts. Consumers: Prompt A, Critic, owner and next run.
STOP: exact merge-readiness then owner phrase; material conflict, repeated seam
failure or evidence cap. NEXT: guarded merge/post-merge readback only after gate.
REPLAN_TRIGGER: repeated blocker, impossible cheapest falsifier, second provider
pivot, cap breach or required new science/representation/infrastructure.

Cheapest falsifier: 65 distinct eligible historical hypotheses through ordinary
public persist/freeze; exact close beyond the ranked set must still refuse.
Evidence budget: fixed16 native core generator calls, up to4 two-cycle/transfer
calls and up to8 one-cycle repair calls, hard28 total. Engineering reviews and
existing per-session Critic caps are separately measured. Fixtures/oracles and
allocation freeze before native calls. Existing client-native isolated agents
only; no new API, package, account or paid transport. Disposable synthetic
stores only. Model/seed control unavailable -> UNKNOWN.

Stages A-E are internal phases of this atom, without routine owner approvals.
Use PR388 projector, time/lineage owners, guard/admission/store/evaluator and
recovery. Keep legacy packet1.0-1.4/snapshot1.0 readers unchanged; fresh1.5/1.1
inherits1.4 grounding. Do not weaken caps, scientific identity, typed close
authority or full-scope guards. Do not edit CI/settings/history/retention/live.
Routine GitHub task-branch transport is authorized by the base harness.

Factory Fit: FULL_REVIEW. Tool Entry: existing delivery-harness, Git/gh, locked
runtime, deterministic fixture owners and isolated client agents suffice;
CAPABILITY_RADAR_NOW=NONE. Product horizon NOW=this atom;
WATCH=order-preserving representation only after a paired measured bottleneck.
Market alpha, chronology and live economics: NOT_EVALUATED.

Entry owner localization: forge_input_receipt._prior_memory_ok also builds the
legacy full snapshot before ordinary preflight. Its direct source consumer is
included to remove the same archive-capacity dependency, not to bypass readiness.

Delivery integration: owner confirmed PR389 merged at0f89ffd8018c05fbafaf79ef609c7dadf888807f. Ordinary merge preserves PaperPlane source changes; only shared Catalog/navigation conflicts require generated propagation. Original scientific/native evidence remains bound to its recorded PR388/capability frames. No Forge source rewrite, native reroll or authority expansion.

CI consumer repair: the first complete PR390 run identified the legacy capsule
schema fragment path, an obsolete packet-version expectation, a test-only
preflight copy inside grounded evidence, and torn-import readiness ordering.
The two exact direct-consumer test paths above are added for this bounded DoD
repair. Preserve strict legacy/fresh branches, the whole-packet bound and typed
source-integrity failures after successful market admission. Native inputs,
outputs, counters and measured historical capability frames remain immutable.
