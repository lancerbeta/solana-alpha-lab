---
task_id: FORGE_PACKET_CAPACITY_RESUME_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 88763e400e5dac7462e70275b23b74e061410445
  expected_upstream: origin/main
  expected_upstream_oid: 88763e400e5dac7462e70275b23b74e061410445
  expected_branch: codex/forge-packet-capacity-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair operational Forge packet capacity across preflight, persist, freeze, isolated handoff, revision/runner-up and cold read without scientific-policy changes; after accepted delivery resume exactly saved MAIN 7805D0BDB4432682C450578B66F060F31E21C578 through independent Critic and native lifecycle without a new market calculation.
managed_write_set:
- docs/tasks/FORGE_PACKET_CAPACITY_RESUME_V1.md
- src/solana_alpha_lab/factory/hfic_packet_capacity.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_generation_context.py
- src/solana_alpha_lab/factory/hfic_prior_memory.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_representation_probe.py
- scripts/hypothesis_forge.py
- scripts/hypothesis_fast_lane.py
- configs/hypothesis_forge_independent_critic_v1.yaml
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- tests/test_forge_evidence_guided_generation_v1.py
- tests/test_hfic_forge_prior_context_capacity_repair_v1.py
- tests/test_hfic_critic_prior_memory_closure_v1.py
- tests/test_hfic_operational_packet_guard_simplification_v1.py
- tests/test_hfic_cli.py
- tests/test_hfic_session.py
- tests/test_hfic_operational_closure_v1.py
- tests/test_hfic_operational_memory_quarantine_v1.py
- tests/test_live_cohort_to_forge_operational_closure_v1.py
- tests/test_normalized_trajectory_probe_preregistration_v1.py
- tests/test_forge_downside_readout_v1.py
- tests/test_hfic_reopened_prior_search_routing_v1.py
- tests/test_hfic_scientific_disposition_continuity_v1.py
- tests/test_hfic_representation_probe.py
- tests/test_forge_evidence_identity_and_owner_gold_v1.py
- tests/fixtures/forge_evidence_guided_generation_v1/**
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- docs/contracts/forge_evidence_guided_generation_v1.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- docs/evidence/forge_packet_capacity_resume_v1/**
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
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_REAL_RESEARCH_STORE_MUTATIONS_BEFORE_ACCEPTED_VERSION_EXCEPT_AUTHORIZED_LOCAL_RECOVERY_COPY
- NO_NEW_REAL_MAIN_ADAPTIVE_PREVIEW_FOCUS_STORE_RUN_OR_SCIENTIFIC_POLICY_CHANGE
- NO_PROVIDER_VPS_COLLECTOR_PRODUCTION_DEPLOY_WALLET_MONEY_OR_HOLDOUT
- STOP_ON_MATERIAL_SCIENTIFIC_OR_AUTHORITY_CONFLICT
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/forge_evidence_guided_generation_v1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_packet_capacity_resume_v1/completion.json
    - docs/evidence/forge_packet_capacity_resume_v1/independent-review.json
    - docs/evidence/forge_packet_capacity_resume_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# FORGE_PACKET_CAPACITY_RESUME_V1

Owner authority: direct bounded repair and continuation request of 2026-10-18.
ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: PRD_LITE in this contract only.
Route/actor: DIRECT_CODEX_DELIVERY/CODEX. Effort: SOL_XHIGH.
CAPABILITY_RADAR_NOW: NONE; existing Python/JSON/native ResearchStore suffice.

DECISION_DELTA: technical working-view recommendations no longer masquerade
as hard limits on mandatory scientific closure. One common operational capacity
resolver provides broad defaults and local overrides without a PR.
UNCERTAINTY_REMOVED: whether complete saved evidence survives every actual
serialization/read boundary and retains identity on resume.
CAPABILITY_OR_EVIDENCE: self-contained packets, bounded readers, meaningful
resource refusals, and a real independent Critic on the unchanged saved MAIN.
Consumers: Forge generator, independent Critic, native lifecycle and owner.
STOP: one exact-head merge gate; after merge continue under already granted
science authority until native review/classification result or a real gate.
NEXT: isolated Critic/finalize on the saved result, no market recalculation.
REPLAN_TRIGGER: scientific semantics, new subsystem/dependency, inability to
preserve mandatory evidence or an unresolved identity/protection conflict.

Implementation/verification in one atom:
- Separate optional recommendation from hard resource protection. Assemble all
  mandatory closure before testing the actual complete serialization; optional
  output stays bounded even with extra headroom. Support >64 mandatory sources.
- Use one common resolver for preflight/context/session/CLI bounds. Bound actual
  file reads. Freeze saves applicable packaging settings; cold replay does not
  reselect memory under today's defaults. New artifacts carry honest hashes/code.
- Extend existing fixtures/checks for real failing shape plus six priors,
  primary/runner-up/revision, serialize-file-read (escaping/Unicode/outer JSON),
  growth beyond old ceilings, corrupt/missing source refusal, small-cap refusal,
  operational override and idempotent restart.
- Targeted development checks, isolated risk-routed review, ordinary harness
  evidence/sync/preflight-push/PR/exact-head CI/readiness. No pre-PR full gate.
- After accepted version, reuse operation
  7e4ff68ec0716a18f31049bcc20dee268b24d3327ee387cedb60a24ee9412752,
  result SHA 39028f4afacd8c0af9575ee37bf0447be10c19f147fda56bcb62ce9114d68c87,
  original cutoff/query/scope/Scout exposure and existing accounting.
  Real MAIN delta must remain zero; report genuine Critic and resolver outcome.

Acceptance oracle: immutable source hashes, native full-archive/source guards,
actual public lifecycle readbacks and an independent packet-only Critic.
A positive scientific verdict is not required. Resource refusal is technical,
specific and actionable, never alpha absence, search exhaustion or generic
HFIC_PROTOCOL_INVALID. No test-count target or extra report project.

Recovery: only nine named Temp files copied and hash-checked into the existing
local forge_operator_results operation area; no data-root clone. Keep recovery
and original result; no reset/quarantine/receipt rewrite. Roll back code by
ordinary revert; append-only research artifacts retain their historical bindings.
