---
task_id: HFIC_MARKET_EVIDENCE_EPOCH_DECISION_BASIS_V2
task_version: '1.0'
status: READY
as_of: '2026-10-01'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 68b986e12e5752d36b3cc2e14d85a855fa90b09f
  expected_upstream: origin/main
  expected_upstream_oid: 68b986e12e5752d36b3cc2e14d85a855fa90b09f
  expected_branch: codex/hfic-market-evidence-epoch-decision-basis-v2
  dirty_mode: ALLOW_REPORTED
objective: >-
  Scientific market basis V2 excludes publication wrapper identities while
  retaining verified integrity provenance, decision-bearing A3/PIT evidence,
  and fail-closed V1 scientific budget continuity without historical mutation.
managed_write_set:
  - docs/tasks/HFIC_MARKET_EVIDENCE_EPOCH_DECISION_BASIS_V2.md
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - scripts/hypothesis_forge.py
  - src/solana_alpha_lab/factory/forge_input_receipt.py
  - tests/test_hfic_market_evidence_epoch_decision_basis_v2.py
  - tests/test_forge_evidence_identity_and_owner_gold_v1.py
  - tests/test_hfic_search_budget_epoch_guard_v1.py
  - tests/test_hfic_preflight.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - tests/test_forge_input_truth_and_visibility_v1.py
  - tests/test_forge_representation_ladder_v1.py
  - tests/test_live_cohort_vanilla_owner_path_v1.py
  - tests/test_hfic_temporal_result_coherence_v1.py
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/reports/hfic_market_evidence_epoch_decision_basis_v2/a1_owner_readout_v1.md
  - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_readonly_budget_v1.json
  - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_factory_fit_v1.json
  - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_semantic_premise_packet_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_CORPUS_REPAIR
  - REAL_DATA_PLANE_MUTATION
  - C4_IMPORT_OR_REAL_C4_ACCESS
  - SCIENTIFIC_FORGE_RUN
  - HISTORICAL_RECEIPT_REWRITE
  - SCIENTIFIC_QUOTA_EXPANSION
  - PROVIDER_OR_VPS_OR_DEPLOY
  - GENERIC_IDENTITY_FRAMEWORK
  - UNPROVEN_CONTINUITY_GRANTS_NEW_TRIAL
  - MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-EVIDENCE-IDENTITY-001, MODULE-HFIC-PREFLIGHT-ADMISSION-001, MODULE-FORGE-INPUT-RECEIPT-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/tasks/FORGE_EVIDENCE_IDENTITY_AND_OWNER_GOLD_V1.md
      - src/solana_alpha_lab/factory/hfic_evidence_identity.py
      - src/solana_alpha_lab/factory/hfic_preflight.py
      - src/solana_alpha_lab/factory/forge_input_receipt.py
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_market_evidence_epoch_decision_basis_v2/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_MARKET_EVIDENCE_EPOCH_DECISION_BASIS_V2

ENTRY_DECISION: START_AS_WRITTEN. MODEL_EFFORT: SOL_XHIGH.
Factory Fit: FULL_REVIEW. SPEC_ROUTE: DESIGN_SPEC (contained here).
Reuse: WRAP existing A3 integrity enumeration and shared identity/admission;
no dependency/plugin/connector/automation adoption. Deterministic scripts:
current Delivery Harness, focused unittest, existing Git/gh CLI.

## Task outcome

- DECISION_DELTA: publication/schema republish cannot authorize new science;
  changed immutable market/PIT/eligibility evidence can create a new market.
- UNCERTAINTY_REMOVED: whether a root/clock change or V1-to-V2 migration
  creates fresh AUTO/focus capacity on scientifically identical evidence.
- CAPABILITY_OR_EVIDENCE: one V2 projection, verified publication provenance,
  conservative compatibility bridge, production-shaped regression family,
  and read-only current C1-C3 budget comparison.
- Consumer: A3 Forge input, HFIC preflight/admission, budget readout, future
  separately authorized LIVE corpus schema-drift atomic repair.
- Cheapest falsifier: imported_at-only change or basis version migration
  frees an already consumed AUTO/focus slot.
- STOP: exact-head CI plus ready_for_owner_phrase=true; no merge.
- NEXT: LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2 after this atom's merge.
- REPLAN_TRIGGER: proof needs historical rewrite, real data repair, quota
  changes, provider access, new generic identity infrastructure, or unknown
  continuity is mistaken for capacity.
- Evidence budget: synthetic production imports/seals and focused consumer
  tests, one read-only real C1-C3 comparison, four independent review roles.
- Product horizon / capability radar NOW: NONE. WATCH: separately authorized
  metadata repair must retain the V2 scientific projection and integrity gates.

## Scientific identity and integrity design

The existing identity owner retains market_evidence_epoch_sha256. Explicit
MARKET_EVIDENCE_BASIS_V2 hashes a scientific projection, while the existing
verified A3 manifest/fingerprint/PIT digest and full-label projection remain
publication provenance. Invalid current root, parquet, lineage or receipt
cannot be hashed as a new market.

Trace A3 selection and packet consumers: logical dataset identity, effective
evidence role/yield/base-X/missingness/feature usability/terminal/hint/families,
confirmatory reuse prohibition, accepted hypothesis and discovery coverage;
verified immutable cohort release/content bindings; partition logical content,
row count and row event/strategy-availability bounds. Row logical content and
immutable release bindings cover source PIT/schedule semantics. Manifest
first_reliable_available_at is publication availability (cannot predate
created_at), not row availability, and remains provenance. Publication IDs,
schema hashes and creation clocks are excluded from scientific hashing.
Schedule semantics are bound by immutable released content plus partition PIT
and row availability; missing required evidence is an incomplete basis.

## V1 continuity

Historical records remain append-only. The exact validated current V1 basis
hash can prove a V1 stamped session belongs to the current V2 market. A frozen
V2 scientific projection can prove equality/difference independently of its
publication provenance. A verified frozen V1 basis can prove different cohort
or immutable source scope; wrapper/label-digest differences alone cannot prove
different scientific scope. Such ambiguous continuity returns a typed STOP,
never an empty budget. Untagged legacy combined receipts retain predecessor
read-only disposition rules and never gain scientific authorization.

All production budget/admission consumers must receive the current validated
basis. Compatibility must cover both quota counting and occupied scientific
slots; same focus must not become a second look through a new algorithm hash.

## Acceptance and non-goals

Synthetic production-shaped tests cover administrative clocks and schema/root
republish invariance, effective eligibility changes, new synthetic cohort,
immutable source/PIT changes, parquet/lineage corruption, capability-only
changes, proven and ambiguous V1 migration, and append-only history.
Current real C1-C3 AUTO/focus usage before and after must match; use read-only
store/metadata access, no Prompt A/B/C, no session or look creation, no C4.
No LIVE corpus repair implementation/execution, estimand/quota changes,
provider/VPS/deploy, release/parquet rewrite or generic identity framework.

Architecture review explicitly answers publication-only budget reset,
integrity-as-new-market, disappearing V1 occupancy, and genuinely new cohorts.
Rollback: ordinary Git revert; never erase or rewrite ResearchStore history.
