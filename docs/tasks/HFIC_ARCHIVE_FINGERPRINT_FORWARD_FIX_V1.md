---
task_id: HFIC_ARCHIVE_FINGERPRINT_FORWARD_FIX_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: df2112d26869a76c704f34afed2d1606bac4e5c0
  expected_upstream: origin/main
  expected_upstream_oid: df2112d26869a76c704f34afed2d1606bac4e5c0
  expected_branch: claude/hfic-archive-fingerprint-forward-fix-v1
  dirty_mode: ALLOW_REPORTED
objective: Restore frozen prior-memory working views after PR 418 added readout projections (research_scope, scientific_identity) to the fragment shelf summary, so the C6 classification-correction runbook can proceed.
managed_write_set:
- docs/tasks/HFIC_ARCHIVE_FINGERPRINT_FORWARD_FIX_V1.md
- src/solana_alpha_lab/factory/hfic_generation_context.py
- tests/test_research_fragments_v1.py
- docs/evidence/hfic_archive_fingerprint_forward_fix_v1/**
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
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_CANONICAL_WRITE_IN_THIS_PR
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/episode_native_required_outcomes_v1.md
    - docs/operator/RESEARCH_FRAGMENTS_V1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/hfic_archive_fingerprint_forward_fix_v1/completion.json
    - docs/evidence/hfic_archive_fingerprint_forward_fix_v1/independent-review.json
    - docs/evidence/hfic_archive_fingerprint_forward_fix_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# Frozen archive fingerprint forward-fix

Owner request (2026-10-21) after the post-merge C6 runbook step 1 stopped.
Forward-fix of PR #418 (merged df2112d2), not a new scope.

DECISION_DELTA: frozen working views remain valid when the shelf summary gains
readout projections; the C6 runbook can continue. UNCERTAINTY_REMOVED: cause of
GENERATION_CONTEXT_MATERIAL_SOURCE_CHANGED. CAPABILITY_OR_EVIDENCE: one fingerprint
owner change, a minimal invariance test and a real read-only fingerprint match.
STOP: exact-head CI, merge readiness, owner phrase. NEXT: C6 runbook from step 1.
REPLAN_TRIGGER: another frozen-source mismatch after this fix.

Cause, proven read-only on the canonical root: the C6 working view froze
`eligible_archive_sha256` 6a2443d9…. PR #418 added `research_scope` and
`scientific_identity` to `research_fragments._summary`. `enrich_prior_capsules`
places that summary in the HFIC-CAND-297E8EF0F13F capsule (RFV-8228C940), so
`archive_fingerprint` became 88969e89… and every earlier frozen view with that
capsule reported a changed material source. Dropping the two keys gives
6a2443d9… again.

Fix: `archive_fingerprint` (single owner, all four uses) hashes capsules
with those two fragment-summary readout projections removed. They project the
same hash-bound result, whose `result_sha256` stays in the fingerprint, so integrity is
unchanged. The prior capsule still carries the comparator. Frozen views are not
rewritten. Rollback: revert, which brings back the frozen-view mismatch.

Evidence: unit invariance test (projections do not move the fingerprint; a result
hash change does). Real canonical root on fix code: current fingerprint
6a2443d9… equals frozen. `forge-run --no-write` binds BASE to
HFIC-SESS-78F92D0FE3E6BC8E with the expected historical readback block
(SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING: the KILL completion was recorded
under capability 79948a83, current 1ba7e1e9). The correction re-binds the current
capability (covered by the PR #418 drift test).
