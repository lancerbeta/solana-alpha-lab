---
task_id: HFIC_REOPENED_PRIOR_SEARCH_ROUTING_V1
task_version: '1.0'
status: READY
as_of: '2026-09-15'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 5c95ad4b7d753fc04dddc43560a1485d812fa15e
  expected_upstream: origin/main
  expected_upstream_oid: 5c95ad4b7d753fc04dddc43560a1485d812fa15e
  expected_branch: cursor/hfic-reopened-prior-search-routing-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close the CONTROL routing hole where reopenable Git parks (H11/H13) were
  ledger-visible but absent from search-memory and Prompt A received ranked
  prior IDs without compact bodies. Commission canonical non-HFIC
  HYPOTHESIS_VERSION records from current Git evidence and require
  one-to-one ranked prior bodies in FORGE_CONTEXT_PACKET. Do not rewrite
  HFIC-SESS-8F4A703030408365; plan its exact-session quarantine via existing
  memory policy. No real RDP write, no new Forge slash, no merge.

managed_write_set:
  - docs/tasks/HFIC_REOPENED_PRIOR_SEARCH_ROUTING_V1.md
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_prior_memory.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - scripts/hypothesis_forge.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_reopened_prior_search_routing_v1.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_legacy_science_rebase.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/hfic_reopened_prior_search_routing/a1_owner_readout_v1.md
  - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_factory_fit_v1.json
  - docs/evidence/hfic_reopened_prior_search_routing/a1_active_rdp_preview_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

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
  - HISTORICAL_SESSION_REWRITE
  - NEW_RANKER_OR_MAX_RANKED_PRIORS_CHANGE
  - PACKET_LIMIT_RAISE
  - PRIOR_MEMORY_BOUND_RAISE
  - NEW_DATABASE_OR_SERVICE
  - TRAJECTORY_CHALLENGER_EXECUTED
  - PROVIDER_API_RPC_WSS_REQUIRED
  - C2_IMPORT
  - H11_H13_SCIENTIFIC_VERDICT
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
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
      - catalog/schemas/hypothesis_critic_input_v1.schema.json
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_reopened_prior_search_routing/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
      - docs/evidence/hfic_reopened_prior_search_routing/a1_active_rdp_preview_v1.json
---

# HFIC_REOPENED_PRIOR_SEARCH_ROUTING_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=NONE.

Independent review roles: `CODE_REVIEWER`, `GOAL_DOD_CRITIC`,
`ARCHITECTURE_CRITIC`. Launch `owner-ux-critic` because CLI/operator preview
changes; do not invent a noncanonical evidence-schema role name.

## DECISION_DELTA

Reopenable legacy parks become faithful non-HFIC search-memory records, and
Prompt A receives a compact body for every ranked prior ID. Defective CONTROL
`HFIC-SESS-8F4A703030408365` stays immutable audit evidence and is planned for
exact-session quarantine via existing memory policy after merge.

## UNCERTAINTY_REMOVED

Whether `NO_WORTHY_HYPOTHESIS` on that CONTROL was a C1 scientific close or a
routing hole (ledger-visible parks without HV bodies / ID-only Prompt A).

## CAPABILITY_OR_EVIDENCE

Deterministic adapter + CLI preview/apply. Read-only active-RDP preview must
reach `CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION`. No live RDP mutate.

## STOP

Exact owner merge gate after CI and merge-readiness. No merge in this atom.
No `/hypothesis-forge`. No Critic. No trajectory probe.

## NEXT

Post-merge local commissioning then owner `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`.

## Root-cause boundaries (proven before implementation)

A. Parks reach `closed_family_ledger` via Git scrape/`classify_source_payload`;
   search-memory is only ResearchStore `HYPOTHESIS_VERSION`.
B. Prompt A packet currently carries `ranked_prior_candidate_ids` as IDs only.
C. Ranker scores store bodies internally; packet can still omit those bodies.
D. Session `HFIC-SESS-8F4A703030408365` HV cards remain eligible until exact
   quarantine; they are not in the current 13-session quarantine set.
E. `START_NEW_SESSION` requires a new evidence epoch (non-HFIC prior append)
   and/or new `memory_eligibility_sha256`; same epoch+focus+eligibility+mode
   returns the old session; AUTO budget is 1 per epoch+eligibility.
