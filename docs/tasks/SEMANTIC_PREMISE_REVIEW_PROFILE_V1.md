---
task_id: SEMANTIC_PREMISE_REVIEW_PROFILE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: cba574f19ed8c6f255488127eced8991f3773b43
  expected_upstream: origin/main
  expected_upstream_oid: cba574f19ed8c6f255488127eced8991f3773b43
  expected_branch: cursor/semantic-premise-review-profile-v1
  dirty_mode: ALLOW_REPORTED
objective: Extend ARCHITECTURE_CRITIC with a bounded SEMANTIC_PREMISE review
  profile and deterministic packet so high-risk premise defects are attacked
  without a fourth merge role or owner-gate change.
managed_write_set:
- docs/tasks/SEMANTIC_PREMISE_REVIEW_PROFILE_V1.md
- configs/semantic_premise_review_profile_v1.yaml
- catalog/schemas/semantic_premise_review_packet.schema.json
- catalog/schemas/catalog_manifest.schema.json
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- src/solana_alpha_lab/semantic_premise_review.py
- scripts/semantic_premise_review_cli.py
- .cursor/agents/architecture-critic.md
- .cursor/commands/delivery-review.md
- .agents/skills/delivery-harness/SKILL.md
- tests/test_semantic_premise_review.py
- tests/fixtures/semantic_premise/false_global_closure.json
- tests/fixtures/semantic_premise/bounded_closure_pass.json
- tests/fixtures/semantic_premise/unknown_as_negative.json
- docs/PROJECT_MAP.md
- docs/evidence/semantic_premise_review_profile/a1_delivery_completion_evidence_v1.json
- docs/evidence/semantic_premise_review_profile/a1_delivery_independent_review_v1.json
- docs/evidence/semantic_premise_review_profile/a1_delivery_factory_fit_v1.json
- docs/reports/semantic_premise_review_profile/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- FRESH_ISOLATED_ARCHITECTURE_REVIEW_NOT_GUARANTEED
- MERGE_EVIDENCE_REQUIRES_BROAD_REDESIGN
- EXTERNAL_SERVICE_REQUIRED
- OWNER_ATTENTION_REDESIGN_REQUIRED
- SECOND_REVIEW_FRAMEWORK_EMERGING
- TRIGGER_REQUIRES_NLP
- FORGE_HARNESS_CYCLIC_DEPENDENCY
- CONTROL_PLANE_EXPANSION_DISPROPORTIONATE
- WALLET_BUILD_EXECUTE_TRANSACTION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/semantic_premise_review_profile/a1_delivery_completion_evidence_v1.json
    - docs/evidence/semantic_premise_review_profile/a1_delivery_independent_review_v1.json
    - docs/evidence/semantic_premise_review_profile/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SEMANTIC_PREMISE_REVIEW_PROFILE_V1

SEMANTIC_PREMISE_HIGH_RISK: true

## SPEC_ROUTE

`BOTH` — owner execution packet is PRD+SSD; this file is the exact Git task
contract.

## DECISION_DELTA

Extend isolated `ARCHITECTURE_CRITIC` with `SEMANTIC_PREMISE` profile + bounded
packet so premise/authority defects are attacked without a fourth merge role.

## UNCERTAINTY_REMOVED

Whether epistemic premise review can be added without enlarging merge authority
or owner ritual. Expected: yes via architecture-critic profile.

## CAPABILITY_OR_EVIDENCE

Deterministic classify + packet + critic profile + synthetic smoke proving
false global closure blocked and bounded closure may PASS.

## NON-GOALS

No fourth review role; no owner-gate change; no Forge runtime change; no
external model service; no NLP trigger; no semantic-route authority.
