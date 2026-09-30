---
task_id: FORGE_CANDIDATE_COLD_LIFECYCLE_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-30'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CLAUDE_CODE_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 860c98abd7f67105a32160de82813fbce3c61c7a
  expected_upstream: origin/main
  expected_upstream_oid: 860c98abd7f67105a32160de82813fbce3c61c7a
  expected_branch: claude/forge-candidate-cold-lifecycle-repair-v1
  dirty_mode: FORBIDDEN

objective: >-
  Make a durable completed ordinary candidate session readable by a fresh
  process and provable by reference. One authoritative scientific-negative
  terminal family owns ordinary completed-session discovery, so a committed
  KILL_MECHANISM is selected like NO_WORTHY and KILL_DUPLICATE instead of
  falling back to a stale frozen draft. One authoritative candidate
  reference-completeness owner replaces the retired len(candidates) >= 4
  rule, so a valid one-candidate session proves and an incomplete one still
  fails closed.

managed_write_set:
  - docs/tasks/FORGE_CANDIDATE_COLD_LIFECYCLE_REPAIR_V1.md
  - docs/evidence/forge_candidate_cold_lifecycle_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_candidate_cold_lifecycle_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_candidate_cold_lifecycle_repair/a1_delivery_factory_fit_v1.json
  - docs/evidence/forge_candidate_cold_lifecycle_repair/trust_smoke_delta_v1.json
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - tests/test_hfic_candidate_cold_lifecycle_v1.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - LIVE_RESEARCH_STORE_MUTATION
  - NEW_SCIENTIFIC_LOOK
  - NEW_PROVIDER_OR_DATA_CALL
  - EXPERIMENT_DEPLOY_OR_MONEY
  - REOPEN_CLOSED_355
  - SCOPE_WIDENING_BEYOND_TWO_P1
  - MERGE_BEFORE_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_session.py
      - src/solana_alpha_lab/factory/hfic_representation_ladder.py
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: NONE

DECISION_DELTA: >-
  Ordinary completed-session discovery reads the canonical
  KNOWN_SCIENTIFIC_NEGATIVES family instead of a hand-maintained pair.
  candidates_retrievable answers whether the candidate references this exact
  session claims durably resolve, never whether it produced at least N
  candidates.

UNCERTAINTY_REMOVED: >-
  Whether a committed one-candidate KILL_MECHANISM lifecycle is discoverable
  cold without regenerating work, and whether a legitimate 0..6 candidate
  portfolio can be proved while a broken candidate reference still fails
  closed.

CAPABILITY_OR_EVIDENCE: >-
  One terminal family for ordinary completed-session selection. One
  candidate_reference_gaps owner used by both the shown payload and the
  store reference check, which no longer skips verification when fewer
  durable cards were found than claimed. Verticals for one-candidate KILL
  and PASS, a historical four-candidate portfolio, broken-reference
  negatives, and one unmocked durable CLOSED replay/new-spec CLI pair.

STOP: >-
  Stop at exact-head merge-readiness. The live ResearchStore stays read-only.
  Do not merge before the owner phrase.

NEXT: >-
  After merge this repair atom ends. The next product action is a supervised
  scientific episode, not another reliability improvement.

Reproduced before the patch on the saved smoke stores at base
860c98ab: `e1_kill/rdp` cold forge-run exits 2 with
SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING and a stale SAVED_DRAFT_PRESENT
stage; `g_saved_work/rdp` prove-runtime exits 1 with
SESSION_ARTIFACT_MISSING.

Scientific-sidecar disposition continuity stays WATCH, not P1.
Offline synthetic mechanical DocumentRunner invocation is acceptable for
routing and integration validation; market or frozen scientific experiment
execution remains forbidden.
