---
task_id: PREFLIGHT_SHADOW_PIN_DRIFT_V1
task_version: '1.0'
status: READY
as_of: '2026-09-15'
owner: lance
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3d828150fef69d22845602b656bc304452c5dc8b
  expected_upstream: origin/main
  expected_upstream_oid: 3d828150fef69d22845602b656bc304452c5dc8b
  expected_branch: cursor/preflight-shadow-pin-drift-v1
  dirty_mode: FORBIDDEN
objective: >-
  Close the locally knowable class that painted CI red after push in #304 and
  #306: historical acceptance files byte-pin control-plane paths outside
  derived-state, and merge-gate binding checks can hash worktree bytes that
  differ from committed Git blobs (CRLF). Preflight-push must DENY both
  before the first remote push; frozen-commit pin semantics stay exempt.
managed_write_set:
  - docs/tasks/PREFLIGHT_SHADOW_PIN_DRIFT_V1.md
  - scripts/delivery_harness.py
  - scripts/owner_attention_gate.py
  - tests/test_preflight_shadow_pin_drift.py
  - tests/test_delivery_harness_deterministic_finish.py
  - tests/test_delivery_harness_merge_guard.py
  - AGENTS.md
  - .agents/skills/delivery-harness/SKILL.md
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - delivery-harness/templates/portable-core/dot-agents/skills/delivery-harness/SKILL.md
  - delivery-harness/templates/portable-bundle-manifest.json
  - catalog/assets/core.yaml
  - docs/evidence/control/a1_preflight_shadow_pin_drift_completion_v1.json
  - docs/evidence/control/a1_preflight_shadow_pin_drift_review_v1.json
  - docs/evidence/control/a1_preflight_shadow_pin_drift_factory_fit_v1.json
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
  - HISTORICAL_EVIDENCE_MIGRATION_REQUIRED
  - TASK_CONTRACT_SCHEMA_EXPANSION_REQUIRED
  - DETERMINISTIC_FINISH_REDESIGN_REQUIRED
  - CI_ARCHITECTURE_CHANGE_REQUIRED
  - NEW_REVIEW_ORCHESTRATOR_REQUIRED
  - OWNER_AUTHORITY_CHANGE_REQUIRED
  - PRODUCT_RUNTIME_CHANGE_REQUIRED
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
      - docs/evidence/control/a1_preflight_shadow_pin_drift_completion_v1.json
      - docs/evidence/control/a1_preflight_shadow_pin_drift_review_v1.json
      - docs/evidence/control/a1_preflight_shadow_pin_drift_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PREFLIGHT_SHADOW_PIN_DRIFT_V1

## Objective

GitHub/CI must stop acting as a linter for two locally knowable classes:

1. Shadow pins: `docs/evidence/**/*.json` records `{path, sha256}` whose
   `path` is in the candidate diff, the pinning evidence file is **not** in
   that diff (SEPARATE), and the pin does not match committed bytes at HEAD.
2. Worktree/committed divergence: a candidate path's worktree bytes differ
   from `git show HEAD:path` (typical Windows CRLF vs LF blob).

## Discriminator (validated on #306 pre-repin ground truth)

`SEPARATE + path-in-diff + sha != HEAD blob` caught all four CI-red pins
(a20r1/pulse/owner_gate × AGENTS.md, core.yaml, owner_attention_gate.py)
and one frozen-semantics false positive
(`durable_resume_router_binding_acceptance_v1.json` → AGENTS.md, verified
at frozen commit `061243fd`, not HEAD).

Frozen-commit evidence files are exempted by a harness-level registry, not
a per-task list and not by migrating historical JSON.

## Scope

- A: `_preflight_shadow_pin_problems` orchestrated by `preflight_push`.
  Check key `shadow_pins_current`. Reason `SHADOW_PIN_DRIFT:<evidence>-><path>`.
- B: `_preflight_worktree_committed_divergence`. Check key
  `worktree_matches_committed`. Reason `WORKTREE_COMMITTED_DIVERGENCE:<path>`.
- C: `bound_delivery_evidence` hashes `implementation_bindings` via
  `git show <head>:<path>` (same committed-byte rule as bind-evidence).
  FakeRunner already implements `git show`; production uses blob bytes.

## Non-goals

No historical evidence rewrite. No task-contract schema field for
exemptions. No new orchestrator. No CI architecture change. No product
runtime change. Portable stdlib-only core still has no `preflight-push`
command (atom A qualification stands).

## Task Outcome Brief

DECISION_DELTA: preflight becomes the local linter for shadow-pin drift
and worktree/blob divergence; merge-gate bindings follow committed bytes.
UNCERTAINTY_REMOVED: whether #304/#306 CI-red class is detectable before
the first remote push, without 110 false DENYs from historical frozen pins.
CAPABILITY_OR_EVIDENCE: two new preflight checks + committed-byte binding
compare, with a two-file frozen-semantics registry.
STOP: listed stop conditions; merge-readiness STOP for owner; no merge.
NEXT: owner phrase on unchanged PR/head.
NON_GOALS: as above.
