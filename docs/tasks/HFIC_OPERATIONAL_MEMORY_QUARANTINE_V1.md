---
task_id: HFIC_OPERATIONAL_MEMORY_QUARANTINE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-09'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 94c3397acf68516d69808e224fb61c4f99142a55
  expected_upstream: origin/main
  expected_upstream_oid: 94c3397acf68516d69808e224fb61c4f99142a55
  expected_branch: cursor/hfic-operational-memory-quarantine-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Turn HFIC calibration-memory reset into a reusable no-Git operational
  capability: owner-selected completed HFIC sessions can be excluded from
  future HFIC search memory via append-only ResearchStore policy, without
  rewriting historical bytes, hiding non-HFIC memory, changing evidence_epoch,
  or mutating CLOSE/PARK/F1/F2/F3.

managed_write_set:
  - docs/tasks/HFIC_OPERATIONAL_MEMORY_QUARANTINE_V1.md
  - src/solana_alpha_lab/factory/hfic_memory_policy.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_prior_memory.py
  - src/solana_alpha_lab/factory/hfic_provenance.py
  - scripts/hypothesis_forge.py
  - schemas/research_memory_projection_v1.sql
  - .agents/skills/hypothesis-forge/SKILL.md
  - tests/test_hfic_operational_memory_quarantine_v1.py
  - tests/test_hfic_cli.py
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/hfic_operational_memory_quarantine/a1_owner_readout_v1.md
  - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - ACTIVE_RDP_WRITE
  - REAL_HYPOTHESIS_FORGE_SLASH
  - HISTORICAL_RESEARCH_REWRITE
  - NON_HFIC_MEMORY_HIDDEN
  - EVIDENCE_EPOCH_MUTATED_BY_POLICY
  - PRIOR_MEMORY_BOUND_RAISED
  - CLOSE_PARK_SEMANTIC_CHANGE
  - F1_F2_F3_BEHAVIOR_CHANGE
  - LIVE_SESSION_IDS_BAKED_INTO_GIT
  - PROVIDER_API_RPC_WSS_REQUIRED

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
      - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_operational_memory_quarantine/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_OPERATIONAL_MEMORY_QUARANTINE_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=NONE. Exact owner atom: reusable no-Git HFIC search-memory quarantine.

## DECISION_DELTA

Completed HFIC sessions can be excluded from future HFIC search memory by an
append-only ResearchStore policy (`HFIC_SEARCH_MEMORY_POLICY`). Quarantine is
eligibility only, not scientific rejection, deletion, or supersession. After
this PR merges once, future quarantine/restore requires no Git mutation.

## UNCERTAINTY_REMOVED

Whether a fresh CONTROL search can be unblocked from
`PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED` without rewriting historical HFIC
bytes, hiding non-HFIC memory, changing `evidence_epoch_sha256`, or raising
the 64 bound.

## CAPABILITY_OR_EVIDENCE

Canonical policy module + CLI `memory-policy-status` /
`memory-policy-preview` / `memory-policy-apply --confirm-append-only`.
Central eligibility consumers: `rank_prior_candidate_ids`, `lookup_prior`,
`build_prior_memory_snapshot`. Search identity binds
`memory_eligibility_sha256` except genesis/no-quarantine, which keeps the
historical `search_key`. T1–T13 on disposable ResearchStore. Live RDP apply
is post-merge operational, not this atom.

## STOP

Exact owner merge gate after CI and merge-readiness. No live Forge. No
active RDP write during delivery.

## NEXT

Post-merge operational quarantine of owner-selected completed HFIC sessions
on the active RDP. Not this PR.
