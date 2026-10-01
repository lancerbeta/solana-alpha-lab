---
task_id: FORGE_SCIENTIFIC_DISPOSITION_CONTINUITY_V1
task_version: '1.2'
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
  expected_base: 5f597efd4869297f149ce8718870e7cbfd81bf52
  expected_upstream: origin/main
  expected_upstream_oid: 5f597efd4869297f149ce8718870e7cbfd81bf52
  expected_branch: claude/new-session-kar08u
  dirty_mode: FORBIDDEN

objective: >-
  A new agent with only the repository, the canonical store locator and the
  owner focus finds what was concluded about a saved ordinary question or a
  bounded pre-values search scope, on which basis, and whether that advice
  still applies, without a host-path sidecar or chat history. One
  ORDINARY_SCIENTIFIC_DISPOSITION_V1 RESEARCH_ARTIFACT, one normal writer
  (disposition-record) and one applicability resolver feed both ordinary
  forge-run readback (derived overlay outside receipt_sha256) and the
  pre-values forge_context_packet. Advice never changes spend, admission,
  market identity or the machine next_action.

managed_write_set:
  - docs/tasks/FORGE_SCIENTIFIC_DISPOSITION_CONTINUITY_V1.md
  - docs/contracts/hfic_scientific_disposition_continuity_v1.md
  - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_factory_fit_v1.json
  - docs/evidence/forge_scientific_disposition_continuity/fresh_context_acceptance_v1.json
  - src/solana_alpha_lab/factory/hfic_scientific_disposition.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - scripts/hypothesis_forge.py
  - catalog/schemas/hfic_scientific_disposition_v1.schema.json
  - tests/test_hfic_scientific_disposition_continuity_v1.py
  - tests/test_hfic_scientific_disposition_navigation_v1.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - configs/factory_semantic_operability_v1.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/**
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
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
  - LIVE_RESEARCH_STORE_MUTATION
  - NEW_SCIENTIFIC_LOOK
  - NEW_PROVIDER_OR_DATA_CALL
  - HISTORICAL_SOURCE_RECONSTRUCTION
  - SECOND_LIFECYCLE_OR_ADMISSION_POLICY_CHANGE
  - EXPERIMENT_DEPLOY_OR_MONEY
  - MERGE_BEFORE_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_scientific_disposition.py
      - docs/contracts/hfic_scientific_disposition_continuity_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_scientific_disposition_continuity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: BOTH

Authoritative specification: owner-supplied PRD+SSD
FORGE_SCIENTIFIC_DISPOSITION_CONTINUITY_V1 v1.2 CLOUD_PORTABLE (supersedes
v1.1 and every earlier draft). This contract freezes its delivery slice; the
durable semantic owner is
`docs/contracts/hfic_scientific_disposition_continuity_v1.md`.

DECISION_DELTA: >-
  Authored scientific judgement about ordinary work becomes a first-class,
  append-only store artifact with explicit lineage and a derived
  applicability status, instead of a locator to a workstation sidecar.
  PARK_FAMILY source wording maps to NO_WORTHY_SIMPLE_NEXT plus a scoped
  pause recommendation, never to a family-wide lifecycle state.

UNCERTAINTY_REMOVED: >-
  Whether a fresh process on a relocated disposable store reads the same
  question and search-scope assessments, whether a new look or calculation
  revision degrades stale advice to REVIEW_REQUIRED, whether retries,
  crashes and concurrent successors stay idempotent and fork-free, and
  whether the capsule fits the unchanged Forge packet budget.

CAPABILITY_OR_EVIDENCE: >-
  Module, schema, disposition-record/disposition-show, forge-run overlay,
  preflight capsule, capability-surface registration, Catalog/semantic
  navigation, skill/operator entries (README impact NONE), deterministic V1-V4 tests on
  production-built portable stores, protected-neighbour regressions and an
  isolated fresh-context acceptance attempt.

STOP: >-
  Stop at exact-head merge-readiness with the machine owner phrase. No live
  ResearchStore mutation, no scientific look, no provider call. Real import of
  the three historical assessments is POST_MERGE_OPERATE and NOT_RUN here.

NEXT: >-
  After merge: separately authorized local
  OPERATE: IMPORT_THREE_SCIENTIFIC_DISPOSITIONS on the canonical machine,
  using disposition-record --preview then append with HISTORICAL_IMPORT
  provenance and exact source SHA checks.

AUTHORITY_SEMANTICS: the assessment artifact grants no authority.
`disposition-show` and `disposition-record --preview` are read-only. A
non-preview `disposition-record` appends to the ResearchStore and is allowed
without an extra mid-cycle owner prompt only for the one assessment produced
by an explicitly invoked `/hypothesis-forge` run (existing
ZERO_MID_CYCLE_OWNER_INTERVENTION scope, no wider look/provider/experiment
authority); a standalone write needs an explicit mutation/OPERATE scope; every
HISTORICAL_IMPORT, including the planned import of the three real historical
assessments, is outside the slash cycle and needs a separate explicit OPERATE
authorization.

README semantic impact = NONE: the existing generic bootstrap is sufficient
after the semantic-route update; a feature-specific README entry would
duplicate navigation. (Preserving the historical harness acceptance pin on
README.md is a constraint, not the primary reason.)

FRESH_CONTEXT_ACCEPTANCE: the one bounded attempt was NOT_PASS_NAVIGATION_GAP;
the defect was fixed in this atom and the deterministic navigation regression
covers that exact owner phrasing; fresh-agent behaviour after the fix remains
NOT_PROVEN. Deterministic V1-V4 are the primary proof.

POST_MERGE_ADOPTION_TARGETS (verification targets only, not pre-merge inputs):
journal 58d69e4384549b48a09616ba2e1fb6d947a9dd8d5197e2bb3678c2049fe6cba1;
market ae771cf5c1e7692c007b442c0048e7547005dc09125eeb9eb75e24406e429749;
focus WINDOW_LIQUIDITY_SURVIVAL_15M_TO_4H;
liquidity V4 HFIC-ART-DISCOVERY-BD41C662D377C9D2CD77B2AF6BAD497CCDA70D87
(d0229c58fd60f0c97690e23567acc7dc7cd62805adab83a352bd87ce953c67c4);
price V4 HFIC-ART-DISCOVERY-7E7216842A8C1D302082CD071E555B8761123319
(06abb6faef268e3013baada12f8ddd014e8c5fe6c596fbd2a3892631f1d4f64d);
source SHA liquidity readout 31845ea35a91dc77c18763be9c5060ee8514d512eba4f369e046c9fa65e9dd85,
price readout 5a01e848c7fb81182bb334deaaf231e465fb1a29c3196584ccbe107f918f0bde,
SUPERVISED_FORGE_SCIENCE_01 e26cbc23acbcd5ee5a57bb70226eb171746d509e35f454a6b0ff2612c7a4fd55,
pre-values synthesis a8d32534a436486292fc177bf15f94657d7b73e82bb1287d92459529f3e788c5.
