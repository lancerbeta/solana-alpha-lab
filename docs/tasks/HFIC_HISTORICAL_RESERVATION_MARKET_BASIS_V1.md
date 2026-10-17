---
task_id: HFIC_HISTORICAL_RESERVATION_MARKET_BASIS_V1
task_version: '1.0'
status: READY
as_of: '2026-10-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 13fb33812361c5f8ea1378dbf0251844938a8cd6
  expected_upstream: origin/main
  expected_upstream_oid: 13fb33812361c5f8ea1378dbf0251844938a8cd6
  expected_branch: claude/hfic-historical-reservation-market-basis-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Ordinary OPPORTUNITY_EPISODES preflight stops being blocked by a historical
  orphan reservation whose different market is provable from an existing
  frozen basis, while admission, reservation and readback keep one shared
  identity, spent scientific budget is never returned, and an upstream STOP
  keeps its true reason ahead of a historical selection caveat.
managed_write_set:
  - docs/tasks/HFIC_HISTORICAL_RESERVATION_MARKET_BASIS_V1.md
  - docs/evidence/hfic_historical_reservation_market_basis_v1/**
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - scripts/hypothesis_forge.py
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_market_evidence_epoch_decision_basis_v2.py
  - tests/test_forge_evidence_identity_and_owner_gold_v1.py
  - tests/test_hfic_selection_robustness_gate_v1.py
  - tests/test_hfic_cli.py
  - catalog/assets/**
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/generated/**
  - docs/PROJECT_MAP.md
  - docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
  - STOP_REAL_DATA_PLANE_MUTATION_SESSION_RESERVATION_OR_SCIENTIFIC_LOOK
  - STOP_HISTORICAL_RECEIPT_REWRITE_QUOTA_RESET_QUARANTINE_NEW_FOCUS_OR_STORE
  - STOP_NEW_REGISTRY_CACHE_SCHEMA_MIGRATION_SERVICE_OR_ALTERNATE_CLI
  - STOP_UNPROVEN_CONTINUITY_GRANTS_NEW_TRIAL
  - STOP_VPS_DEPLOY_OR_PROVIDER_CALL
  - REPLAN_IF_A_NEW_SUBSYSTEM_OR_PER_CALLER_FALLBACK_IS_NEEDED
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-EVIDENCE-IDENTITY-001, MODULE-HFIC-PREFLIGHT-ADMISSION-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/tasks/HFIC_MARKET_EVIDENCE_EPOCH_DECISION_BASIS_V2.md
      - src/solana_alpha_lab/factory/hfic_evidence_identity.py
      - src/solana_alpha_lab/factory/hfic_preflight.py
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_historical_reservation_market_basis_v1/completion.json
      - docs/evidence/hfic_historical_reservation_market_basis_v1/independent-review.json
      - docs/evidence/hfic_historical_reservation_market_basis_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# HFIC_HISTORICAL_RESERVATION_MARKET_BASIS_V1

Owner EXECUTE (16.10.2026): small repair of the historical market-basis reader
and of truthful preflight precedence; not a general Forge audit. This contract
is the whole brief (no separate PRD/SSD/plan). ENTRY_DECISION: START_AS_WRITTEN.
MODEL_EFFORT: SOL_XHIGH. SPEC_ROUTE: NONE. Factory Fit: FULL_REVIEW.
Reuse: WRAP the existing shared reservation-basis owner and versioned epoch
validator; no dependency, registry, cache, schema or CLI addition.

Design anchor `13fb33812361c5f8ea1378dbf0251844938a8cd6`. Local read-only
evidence (not committed): reservation `HFIC-SESS-94671572F727012E` stamped
`9343fc57…` has no basis field and no own lifecycle rows; saved session
`HFIC-SESS-72BDEC113DBFD18A` holds a V2 frozen basis recomputing exactly to
that stamp and proves a different (September LIVE_LIFECYCLE) market. The
public preflight showed `BLOCK_FORGE_SELECTION_RISK` while the real refusal was
`MARKET_EPOCH_CONTINUITY_UNRESOLVED`.

## Outcome

- DECISION_DELTA: a provably different-market orphan reservation no longer
  blocks ordinary entry; an upstream STOP keeps its reason over a historical
  selection caveat.
- UNCERTAINTY_REMOVED: whether the canonical reproducer STOP is a scientific
  restriction or a reader defect.
- CAPABILITY_OR_EVIDENCE: one shared reader rule consumed unchanged by
  `epoch_search_budget_usage` and `resolve_scientific_admission`; explainable
  proof source in `search_budget.reservation_market_basis_proofs`.
- Consumer: ordinary OPPORTUNITY_EPISODES preflight/admission (I4 metadata).
- Cheapest falsifier: canonical read-only reproducer on unchanged history.
- STOP: exact-head CI plus `ready_for_owner_phrase=true`.
- NEXT: after merge and the pinned I4 path, read-only merged-reader check on
  the actual corpus; no VPS deploy.
- REPLAN_TRIGGER: per-caller fallback, persistent registry, historical write
  or a new subsystem becomes necessary.

## Rules

Own correct basis and same-lifecycle proof keep priority. Only a reservation
whose `market_evidence_basis` field is ABSENT, with a valid stamp and no own
lifecycle rows, may borrow the frozen basis of saved, identity-valid sessions
stamped with the same epoch whose basis the existing validator recomputes to
exactly that stamp (V1 canonical identity, V2 scientific projection; V2
publication fields may differ). Proofs must share one basis version; the
choice is deterministic by session id, never by date/focus/cohort name. Only
the market description is borrowed. Explicit null, own-history conflict, wrong
hash, missing proof or disagreeing versions keep the exact refusal.

A historical selection caveat creates no new STOP and never replaces the
upstream terminal/budget reason; a gate-created integrity STOP stays.

## Acceptance

A. Canonical reproducer no longer reports a false continuity STOP; budget is
computed, not zeroed; any other real refusal is named.
B. Synthetic production-import vertical: orphan V1 reservation at an old
market, two new cohorts, public preflight, ordinary admission that persists
the generated draft (minimal saved result) and reserves the slot, fresh-process
exact replay and readback without a second spend (independent stamp oracle).
C. Parameterized: two new cohorts plus exact reimport, publication-only change,
same-market occupancy, missing proof/wrong hash/invalid basis/disagreeing versions/own-history
conflict (explicit null already covered), JSON and human next action with upstream STOP plus
caveat.

Rollback: ordinary Git revert of the reader; historical records, receipts and
real reservations are never modified.
