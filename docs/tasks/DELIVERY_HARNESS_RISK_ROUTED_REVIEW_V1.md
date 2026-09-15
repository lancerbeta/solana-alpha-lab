---
task_id: DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1
task_version: '1.0'
status: VALIDATED
as_of: '2026-09-15'
owner: lance
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b1d22d77ab49b95217f8a0d4f4fa28bc2bfbfb21
  expected_upstream: origin/main
  expected_upstream_oid: b1d22d77ab49b95217f8a0d4f4fa28bc2bfbfb21
  expected_branch: cursor/delivery-harness-risk-routed-review-v1
  dirty_mode: FORBIDDEN
objective: >-
  Make machine enforcement of independent-review evidence match the already
  canonical risk-routed review semantics: the exact required role-set is
  frozen by the task contract, strengthened by deterministic floors, and
  enforced identically by bind-evidence, preflight-push, merge-readiness and
  guarded merge through one canonical role resolver.
managed_write_set:
  - docs/tasks/DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1.md
  - catalog/schemas/delivery_harness_task_contract.schema.json
  - catalog/schemas/delivery_harness_independent_review_evidence.schema.json
  - scripts/owner_attention_gate.py
  - scripts/harness_sync.py
  - scripts/delivery_harness.py
  - AGENTS.md
  - .agents/skills/delivery-harness/SKILL.md
  - .cursor/commands/delivery-review.md
  - .cursor/commands/delivery-finish.md
  - .cursor/agents/code-reviewer.md
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - delivery-harness/templates/portable-bundle-manifest.json
  - delivery-harness/templates/portable-core/scripts/delivery_harness.py
  - delivery-harness/templates/portable-core/dot-agents/skills/delivery-harness/SKILL.md
  - delivery-harness/templates/portable-core/dot-cursor/commands/delivery-finish.md
  - delivery-harness/templates/portable-core/dot-cursor/commands/delivery-review.md
  - tests/test_delivery_harness_merge_guard.py
  - tests/test_delivery_harness_context.py
  - tests/test_delivery_harness_skill.py
  - tests/test_harness_sync_bindings.py
  - tests/test_delivery_harness_risk_routing.py
  - tests/test_semantic_premise_review.py
  - tests/test_delivery_harness_deterministic_finish.py
  - catalog/assets/core.yaml
  - docs/evidence/control/a1_delivery_harness_risk_routed_review_completion_v1.json
  - docs/evidence/control/a1_delivery_harness_risk_routed_review_review_v1.json
  - docs/evidence/control/a1_delivery_harness_risk_routed_review_factory_fit_v1.json
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/control/owner_attention_gate_acceptance_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - NEW_REVIEW_ORCHESTRATOR_REQUIRED
  - AI_RISK_CLASSIFIER_REQUIRED
  - REVIEWER_IDENTITY_OR_SIGNATURE_SYSTEM_REQUIRED
  - HISTORICAL_EVIDENCE_MIGRATION_REQUIRED
  - GENERIC_SCIENCE_CRITIC_PROMOTION_REQUIRED
  - CI_ARCHITECTURE_CHANGE_REQUIRED
  - OWNER_AUTHORITY_CHANGE_REQUIRED
  - DETERMINISTIC_FINISH_REDESIGN_REQUIRED
  - TASK_SELECTION_AUTHORITY_CHANGE_REQUIRED
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/control/a1_delivery_harness_risk_routed_review_completion_v1.json
      - docs/evidence/control/a1_delivery_harness_risk_routed_review_review_v1.json
      - docs/evidence/control/a1_delivery_harness_risk_routed_review_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1

## Objective

Machine enforcement must match the canonical risk-routed review semantics:
CODE_REVIEWER always; other roles frozen by the exact task contract according
to canonical triggers and strengthened by deterministic floors. One canonical
resolver computes `effective_required_roles`; bind-evidence, preflight-push,
merge-readiness and guarded-merge consume it identically.

## Scope

- A: optional top-level `required_review_roles` in the task contract schema
  (5 allowed roles, unique, min 1, CODE_REVIEWER mandatory when present;
  absent => LEGACY_TRIPLE; LIVE_PR_HEAD => LEGACY_TRIPLE; no historical
  migration).
- B: single role resolver `effective_required_roles(task_contract, candidate_paths)`
  in `owner_attention_gate.py`.
- C: deterministic floors: CODE_REVIEWER always; ARCHITECTURE_CRITIC added
  when candidate paths touch control/schema/authority surfaces.
- D: CODE_REVIEWER under-scope semantics documented in the code-reviewer
  agent contract; strengthening requires replan, never weakening.
- E: review evidence shape: `review.required_roles == effective_required_roles`
  with exactly one final PASS entry per role; no missing/duplicate/unrelated
  roles; SINGLE_AGENT_REVIEW_FALLBACK stays merge-blocking.
- F: OWNER_UX_CRITIC promoted to first-class in schema/resolver/validator.
- G: optional `remediation_history` (role in final set, prior NOT_READY,
  severity enum, 40-hex SHAs); final truth stays verdict=PASS.
- H: schema_version preserved at 1.0 (additive/backward-compatible).
- I: shared enforcement across bind-evidence, preflight-push,
  merge-readiness, guarded-merge.
- J: doc/adapter convergence (AGENTS.md, SKILL.md, delivery-review,
  delivery-finish, code-reviewer, protocol, portable manifest).

## Managed write set (heading required by legacy tasks)

See the managed_write_set list in the front matter. It includes the exact
schema, script, doc, test and evidence paths listed by the owner packet.
Derived/catalog pins are updated only via sanctioned `harness_sync --apply`
when the pinned hashes change.

## Task Outcome Brief

DECISION_DELTA: review roles become contract-frozen + floor-strengthened
instead of globally fixed triple.
UNCERTAINTY_REMOVED: whether bind/preflight and merge gates resolve the same
role-set for the same candidate (acceptance 12/13).
CAPABILITY_OR_EVIDENCE: risk-routed review enforcement with one resolver.
STOP: none of the listed stop conditions triggers; atom completes at
merge-readiness STOP for owner.
NEXT: owner merges or requests changes.
NON_GOALS: no new orchestrator, no AI classifier, no reviewer PKI, no
historical migration, no SCIENCE_CRITIC promotion, no CI changes, no
product/runtime changes.
