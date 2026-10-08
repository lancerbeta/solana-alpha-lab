---
task_id: FORGE_RESEARCH_FLOW_RELIABILITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-08'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 44eda5d72dccd569e9766a74046ce8b2ec47f417
  expected_upstream: origin/main
  expected_upstream_oid: 44eda5d72dccd569e9766a74046ce8b2ec47f417
  expected_branch: codex/forge-research-flow-reliability-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair the whole ordinary OPPORTUNITY_EPISODES research passage through consumer-compatible cards, truthful routing/prior applicability, exact saved-state recovery and bounded verified reads, proving D01-D18 without scientific acceptance or live work.
managed_write_set:
- docs/tasks/FORGE_RESEARCH_FLOW_RELIABILITY_V1.md
- docs/contracts/forge_research_flow_reliability_v1.md
- docs/evidence/forge_research_flow_reliability_v1/**
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_card_projection.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_research_scope.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/forge_input_receipt.py
- src/solana_alpha_lab/factory/hfic_representation_ladder.py
- src/solana_alpha_lab/factory/hfic_control_integrity.py
- src/solana_alpha_lab/factory/hfic_prior_memory.py
- src/solana_alpha_lab/factory/hfic_suppression_semantics.py
- src/solana_alpha_lab/factory/hfic_memory_policy.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_research_policy.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/prior_work.py
- schemas/research_memory_projection_v1.sql
- scripts/hypothesis_forge.py
- scripts/delivery_harness.py
- tests/test_preflight_shadow_pin_drift.py
- tests/test_research_projection.py
- catalog/schemas/hypothesis_forge_draft_v1*.schema.json
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- catalog/schemas/forge_input_receipt_v1.schema.json
- configs/hypothesis_forge_independent_critic_v1.yaml
- catalog/generated/**
- docs/PROJECT_MAP.md
- catalog/assets/**
- catalog/catalog_manifest.yaml
- docs/generated/**
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_forge_research_flow_reliability_v1.py
- tests/fixtures/forge_research_flow_reliability_v1/**
- tests/test_hfic_session.py
- tests/test_hfic_cli.py
- tests/test_hfic_critic_prior_memory_closure_v1.py
- tests/test_hfic_forge_prior_context_capacity_repair_v1.py
- tests/fixtures/forge_research_flow_reliability_v1/resource_probe.py
- tests/test_forge_representation_ladder_v1.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_NEW_EXACT_OWNER_MERGE_PHRASE
- STOP_REAL_CORPUS_HOLDOUT_PROVIDER_VPS_DEPLOY_CREDENTIALS_MONEY
- STOP_NEW_SUBSYSTEM_DEPENDENCY_OR_SCIENTIFIC_AUTHORITY
- STOP_MATERIAL_TRUTH_CONFLICT
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
    - delivery-harness/policies/solana-alpha-lab.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_research_flow_reliability_v1/completion.json
    - docs/evidence/forge_research_flow_reliability_v1/independent-review.json
    - docs/evidence/forge_research_flow_reliability_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# FORGE_RESEARCH_FLOW_RELIABILITY_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH (this compact contract,
owner-supplied PRD+SSD and the amended flow contract). MODEL_EFFORT_RECOMMENDATION:
SOL_XHIGH. Authority: explicit owner request to implement the attached
SMIAL_FORGE_RESEARCH_FLOW_RELIABILITY_V1_PRD_SSD_2026-10-08.md, one atom/one PR.
Its D01-D18 matrix is the acceptance denominator; no inherited one-bug limit.
Design anchor fd00836ea6066b2c47216e89b0187d1a096f8643 is an ancestor of BASE;
the only intervening change is PR #387's CI timeout. BASE stays fixed.

DECISION_DELTA: ordinary Forge becomes usable without manual persisted-card
repair or false market/family closure. Consumer: owner agent, native generator,
isolated Critic, public CLI and existing session/store/ladder/replay owners.
UNCERTAINTY_REMOVED: authored-field fidelity, downstream shape, prior scope,
interruption recovery, read cost and separate native/mechanical readiness.
CAPABILITY_OR_EVIDENCE: coherent source repair and reproducible D01-D18 proof.
STOP: material boundary or CI/readiness-ready merge approval; no phase approvals.
NEXT: exact owner merge phrase, then guarded merge and post-merge readback.
REPLAN_TRIGGER: repeated same-boundary failure, impossible falsifier, second
provider/route pivot or need for a new subsystem/scientific capability.

Cheapest BASE witnesses: string confounders reach Critic as a string; empty/false
become missing; PIT/dependency aliases disappear; review KILL becomes HARD_CLOSE;
research-policy and ordinary-operation are absent from capability provenance.
Early mechanical entry typos are corrected before packaging evidence.

## Implementation and verification plan

- [x] V1 / D01-D06: parameterized material projector RED -> source fix -> real
  schema/public persist controls; same historical draft recovery; 0/1/10 cards,
  selected9/runner10/revision; canonical prompt/example and effective ceilings.
- [x] V2 / D07-D10: schema-enum terminal oracle; typed suppression/applicability;
  persisted exact/related/PARK/technical/family/new-evidence fixture and public
  BASE/normalized transition with unchanged frozen policy and attempts.
- [x] V3 / D11,D14-D17: production episode fixture/literal numerical oracle;
  passive prefix poison traces; OS interruption/fresh process/moved root;
  corrupt/stale/race controls; paired 40/400 cold read counts/three medians;
  bounded capability mutation and historical repair regression.
- [ ] V4 / D12,D13,D15,D18: actual emitted episode packet -> isolated native
  generator -> unchanged authored draft -> persist/freeze -> isolated Critic ->
  truthful machine endpoint; separate scripted-Critic classify/final/replay;
  packet-only adversarial read; compact evidence index, affected tests, four
  isolated engineering critics, one PR/exact-head CI/readiness.

Evidence: first relevant RED and final GREEN; final readout approximately
5-10 KiB, new machine/human evidence approximately <=150 KiB excluding mandatory
harness bindings/tests. Synthetic table and oracle are fixed before value reads;
N32 repeats are disclosed as dependent templates, never significance/alpha.
Native research outputs target <=6; no reroll for positive. Existing local
agent/review facilities only; engineering reviewers count separately.
GitHub routine transport is authorized; product network/external caps remain zero.
Generated Catalog/navigation is maintained by harness_sync, never hand-edited.
Direct-consumer write-set additions require a short reason here, no micro-approval.

Factory Fit: FULL_REVIEW. Capability radar NOW=NONE: existing locked runtime,
production fixture owners, Git/gh, Harness and isolated agents suffice.
Product horizon WATCH=chronological validation only after separate capability
and scientific authority. No strategy/promotion/live/VPS claim; raw KILL stays KILL.

Direct consumers: prior-memory regression oracles now distinguish a retained
Critic KILL from typed family-close authority; source verdict and scope stay bound.

Direct generated consumers: Catalog generated navigation/PROJECT_MAP follow
harness_sync. The existing Forge config now states frozen-policy precedence
without changing shipped values.

Executed: native3 outputs, lawful KILL retained; positive scripted boundary
with actual classifier/Runner; OS recovery; both reserved intent/result
publication contention repaired using existing retry budget. D15 context
locator is additive refusal detail. All local scoped results are in evidence;
exact CI/readiness/phrase remain delivery gates, not preasserted PASS.

Direct delivery consumers: scripts/delivery_harness.py and its existing shadow-pin
regression register the unchanged grounded-handoff checkpoint as an accepted
44eda5d snapshot. All22 original implementation hashes match that Git snapshot;
byte drift, missing checkpoint/root or unavailable Git blob still DENY. This
uses the existing commit-bound archive owner, preserves native producer IDs and
all historical bytes, and does not widen authority/control prefixes or gates.
Final review remediation also distinguishes verdict authority from ledger state
and preserves saved-context SHA/relative locator through ordinary forge-run.
D09 now has one persisted public exact/related/PARK/technical/typed family-close
matrix, with no helper substitution for candidate/run or historical rewrite.

D10 complete-path review also repairs repeated semantic candidates on admitted
new evidence: session-scoped record IDs, existing explicit record supersession
and transitive linear projection validation, source DEC readback on failover,
and no known-other-session verdict attribution. Candidate/definition identity,
raw old outcomes, budget/admission/family-close authority remain bound.

Direct history read consumers: schemas/research_memory_projection_v1.sql and
src/solana_alpha_lab/factory/prior_work.py bind HYP/DEC/RUN/related prior work
by known session; legacy unbound matches only legacy unbound. Writer lease
checks HYP lineage before immutable publication, so a raced stale predecessor
refuses with zero durable writes. These paths are included to close the same
D10 finding, not to widen the research or evidence authority.
