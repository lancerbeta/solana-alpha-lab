---
task_id: OPPORTUNITY_EPISODES_JUPITER_SWITCH_AND_BIND_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-06'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9efc74c0d57b10addcc4fe31155e2333fbac13c3
  expected_upstream: origin/main
  expected_upstream_oid: 9efc74c0d57b10addcc4fe31155e2333fbac13c3
  expected_branch: claude/jupiter-core-switch-and-bind-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  JUPITER_CORE_COMMISSIONING / SWITCH_AND_BIND: record the already-obtained
  Jupiter parser/route qualification in an append-only provider-route registry
  successor without hiding the failed shared-account overlap, correct the
  operator runbook (exclusive lane plus executed pause, not COMPLETE of all
  history), fix the bootstrap protection procedure, and place the program
  blueprint in the design owner with one operator-route link.
managed_write_set:
- configs/provider_route_capability_registry_v11.yaml
- catalog/schemas/provider_route_capability_registry_v11.schema.json
- src/solana_alpha_lab/provider_route_capability_registry_v11.py
- tests/test_provider_route_capability_registry_v11.py
- tests/test_catalog_canonical_binding_discovery.py
- docs/evidence/opportunity_episodes_jupiter_commissioning_v1/**
- docs/evidence/opportunity_episodes_jupiter_switch_and_bind_v1/**
- docs/design/SMIAL_JUPITER_OPERATING_BLUEPRINT_RUNBOOK_V1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/tasks/OPPORTUNITY_EPISODES_JUPITER_SWITCH_AND_BIND_V1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/fixtures/discovery_gold_queries_v1.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/FACTORY_SEMANTIC_MAP.md
- configs/factory_semantic_operability_v1.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_MERGE_DEPLOY_SETTINGS_TIMER_CHANGES
- STOP_PROVIDER_CALLS_NEW_CREDENTIALS_OR_SECRET_ACCESS
- STOP_PRODUCTION_DATA_REAL_SCIENTIFIC_LOOK_DESTRUCTIVE_CLEANUP
- STOP_SCHEDULER_LIFECYCLE_OR_PROVIDER_RUNTIME_CODE_CHANGE
- STOP_POPULATION_GRID_CAP_FLOOR_OR_NUMERIC_VOCABULARY_CHANGE
context_requirements:
  catalog_asset_ids: [MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010, DOC-OPPORTUNITY-EPISODES-OPERATOR-001]
  l2_roles: [EXTERNAL_ROUTE_KNOWLEDGE, ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: [CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010]
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/opportunity_episodes_jupiter_switch_and_bind_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/opportunity_episodes_jupiter_switch_and_bind_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/opportunity_episodes_jupiter_switch_and_bind_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OPPORTUNITY_EPISODES_JUPITER_SWITCH_AND_BIND_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: NONE (metadata, evidence and
runbook change; no runtime semantics). Route DIRECT_CLAUDE_CODE_DELIVERY, actor
CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH for authority/protection
boundaries; routine readback and transport need no switch. Authority: the
owner's explicit 2026-10-06 instruction (program `JUPITER_CORE_COMMISSIONING`,
phase `SWITCH_AND_BIND`); expected base `9efc74c0` re-verified at Entry as live
`origin/main`.

DECISION_DELTA: a later OPERATE packet can cite a dated, hash-pinned route
qualification instead of a scratch receipt, and cannot mistake it for account
safety or batch-shape proof.
UNCERTAINTY_REMOVED: which Jupiter routes have a parser-compatible HTTP 200
observation, and what that observation does not prove.
CAPABILITY_OR_EVIDENCE: registry v11 (append-only over v10) with receipt-bound
routes `toporganicscore/5m`, `toptraded/5m`, `toptrending/5m` and the search
route; the byte-exact sanitized qualification receipt and a separate limits
record; operator runbook correction; the program blueprint in `docs/design/`.
Consumers: the next OPERATE commissioning packet, the catalog route answer
`SEM-PROVIDER-ROUTES`.
Cheapest falsifier (before any Catalog work): v11 validates against its schema,
preserves 12 v10 route objects byte-semantically, mirrors each receipt call, and
refuses a dropped or upgraded pace limitation.

Required invariants:

- v10 stays byte-identical; the only transition is the v10 placeholder search
  route gaining its first observation, recorded with the superseded object hash.
- The qualification receipt is committed byte-exact; the overlap with the legacy
  collector is a separate `account_pace_discipline` field and the receipt is
  neither corrected nor re-run.
- The search observation claims only the single-object public-mint shape.
- Precedent note: v9 appended new route IDs for new observations; v11 is the first
  same-route-ID transition (placeholder to observed), legitimate because the
  placeholder had no `last_success` and its object hash is recorded.
- Accepted limits: the Catalog binding evidence for 011 is its own validator module (no live
  runtime consumer yet; frozen experiments keep exact v10 pins); the v10 and v11 search route
  share one route ID, so a receipt citing it must also cite registry ID and sha.
- No route grants a call, a credential, a retry, a fallback or a selection.
- The V1 ceiling of 100 admissions per UTC day is documented, not raised.

DoD: v11 registry, schema, validator and tests pass; Catalog binding moves to
v11 with generated views synced; the runbook states exclusive-lane plus executed
pause (not COMPLETE of all history), recorded gaps, bootstrap protection and the
separate canary/deploy/provider/retention authority; the blueprint is reachable
from the operator route; nothing in scheduler, lifecycle or provider runtime
code changes.

Non-goals: deploy, any VPS write, provider call, credential read, activation,
production import, scientific look, floor/grid/numeric-vocabulary change,
overlap repair, retention or cleanup, merge, the stale
`delivery-harness/policies/solana-alpha-lab.md` provider-registry pin (a control
surface, a separate harness atom).
Reuse/build: WRAP the existing append-only successor pattern (v9, v10); no new
framework, dependency or service.
Risks: moving the Catalog binding changes current-registry lookups and gold
queries; frozen experiments keep their exact v10 pins.
Rollback: owner-gated revert of this commit; v10 is untouched.
STOP: merge boundary; never merge in this atom.
NEXT: exact-head CI, merge-readiness, owner phrase. Follow-up atoms (separate): the stale
provider-registry pin in `delivery-harness/policies/solana-alpha-lab.md` (control surface) and
`tests/test_delivery_harness_adapters.py`; the exclusive-lane SEARCH batch observation.
REPLAN_TRIGGER: the transition cannot be expressed append-only, or scope reaches
a scheduler/lifecycle/provider runtime change.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE.

Required reviews: isolated code, goal/DoD and architecture. Architecture must
answer: can a reader of v11 still conclude that Jupiter is account-safe or that
the search path handles a batch of 100, and can a frozen v10 consumer drift?
