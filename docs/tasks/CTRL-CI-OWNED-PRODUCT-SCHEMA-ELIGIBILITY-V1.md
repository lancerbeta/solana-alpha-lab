---
task_id: CTRL-CI-OWNED-PRODUCT-SCHEMA-ELIGIBILITY-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 913760251128f05da8c8a0cfde1db142982c7bc5
  expected_upstream: origin/main
  expected_upstream_oid: 913760251128f05da8c8a0cfde1db142982c7bc5
  expected_branch: cursor/ctrl-ci-owned-product-schema-eligibility
  dirty_mode: ALLOW_REPORTED
objective: Admit typical product catalog task schemas and mechanical test_catalog inventory updates to focused ci-owned delivery while keeping meta/harness validator paths on tracked-only.
managed_write_set:
  - docs/tasks/CTRL-CI-OWNED-PRODUCT-SCHEMA-ELIGIBILITY-V1.md
  - scripts/validate_ci.py
  - tests/test_ci.py
  - delivery-harness/harness.yaml
  - docs/agent/EXECUTION_ROUTER_PROTOCOL.md
  - catalog/assets/core.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - ELIGIBILITY_FALSE_ADMISSION
  - FOCUSED_CHILD_COMMAND_SET_CHANGED
  - LIVE_PR_HEAD_BYPASS_EXTENDED_TO_PRODUCT
  - PROVIDER_OR_NETWORK_CALL
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# CTRL-CI-OWNED-PRODUCT-SCHEMA-ELIGIBILITY-V1

## Task Outcome Brief

- **Owner decision:** typical product write sets that add
  `catalog/schemas/task*_*.schema.json` and mechanical
  `tests/test_catalog.py` inventory updates are bounded product work, not
  validation-runtime changes.
- **Product outcome:** a product PR with those paths and green exact-head CI
  completes guarded-merge primary `--ci-owned-delivery` without entering
  `--tracked-only-delivery`. Focused `wall_seconds` stays under 120; local
  merge path stays under 2 minutes.
- **Named consumers:** `DIRECT_CURSOR_DELIVERY` guarded merge, later ordinary
  product atoms, and `GITHUB_PR_EXACT_HEAD_CI`.
- **Cheapest falsifier:** `catalog/schemas/task30_*.schema.json` plus
  `tests/test_catalog.py` with otherwise ordinary product paths fails
  `validate_ci_owned_delivery_eligibility`, or a meta/harness schema /
  `tests/test_ci.py` is admitted.
- **Terminal outcome:** `PROCEED` only if targeted eligibility tests pass,
  focused child commands stay unchanged, exact-head CI is green, and this
  atom's own merge remains tracked-only because it touches
  `scripts/validate_ci.py`.
- **User-visible result:** ordinary product schema inventory no longer pays a
  local full gate; meta/harness/validator paths still do.
- **Non-goals:** no LIVE_PR_HEAD CI-consumption bypass for product tasks, no
  pytest-xdist, no skipped clone, no GitHub branch deletion, no merge-phrase
  change, no `local/` raw-evidence deletion, no worktree GC automation, no
  provider/network/cash.
- **Evidence budget:** offline repository work only; no local full gate
  before PR; no catalog asset registration.
- **Replan trigger:** false admission of a validator/meta schema, focused
  command-set drift, or inability to keep this atom's own merge on
  tracked-only.

## Decision capsule

- `DECISION_DELTA`: replace blanket `catalog/schemas/` ineligibility with a
  negative meta/harness list; remove `tests/test_catalog.py` from exact
  ineligible paths.
- `UNCERTAINTY_REMOVED`: product task/provider schemas are eligible; catalog
  self-governance and validation-runtime paths remain ineligible.
- `CAPABILITY_OR_EVIDENCE`: eligibility tests plus exact-head CI.
- `STOP`: after green exact-head CI and rebuilt `LIVE_PR_HEAD` context;
  do not merge.
- `NEXT`: owner exact phrase, then guarded merge (tracked-only once for this
  control fingerprint). Ordinary later product atoms use focused primary.
- `SPEC_ROUTE=NONE`

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. This is validation-economy routing, not a
hypothesis-specific code fork. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`. Worktree prune remains operational and is not
automated here.

## Authority and non-claims

Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash,
deployment, settings, destructive/history actions and branch deletion are
not authorized. Passing eligibility, CI or merge does not establish
semantic acceptance, canonical `DONE`, alpha or cashflow.
