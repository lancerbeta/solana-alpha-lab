---
task_id: CTRL-CI-OWNED-PRODUCT-RESEARCH-DDL-ELIGIBILITY-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-26'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 016904b4991a0c8f3e81daf821de90eebf0cea79
  expected_upstream: origin/main
  expected_upstream_oid: 016904b4991a0c8f3e81daf821de90eebf0cea79
  expected_branch: cursor/ctrl-ci-owned-product-research-ddl-eligibility
  dirty_mode: ALLOW_REPORTED
objective: Admit the exact product research-memory projection DDL to focused ci-owned delivery while keeping core/meta schemas/ SQL and validator paths on tracked-only.
managed_write_set:
  - docs/tasks/CTRL-CI-OWNED-PRODUCT-RESEARCH-DDL-ELIGIBILITY-V1.md
  - scripts/validate_ci.py
  - tests/test_ci.py
  - delivery-harness/harness.yaml
  - docs/agent/EXECUTION_ROUTER_PROTOCOL.md
  - catalog/assets/core.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_completion_v1.json
  - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_review_v1.json
  - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_factory_fit_v1.json
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
  - TIMEOUT_CAP_CHANGE
  - LIVE_PR_HEAD_BYPASS_EXTENDED_TO_PRODUCT
  - FOCUSED_CHILD_COMMAND_SET_CHANGED
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
    DELIVERY_EVIDENCE:
      - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_completion_v1.json
      - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_review_v1.json
      - docs/evidence/control/a1_ci_owned_product_research_ddl_eligibility_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-CI-OWNED-PRODUCT-RESEARCH-DDL-ELIGIBILITY-V1

## Task Outcome Brief

- **Owner decision:** repo-root product research-memory projection DDL is
  bounded product inventory, not a validation-runtime change. The measured
  tracked-only fallback timeout is a symptom of the blanket `schemas/` deny;
  do not raise the cap.
- **Product outcome:** a product PR that adds only
  `schemas/research_memory_projection_v1.sql` plus otherwise ordinary product
  paths completes guarded-merge primary `--ci-owned-delivery` and consumes
  existing exact-head CI. Core `schemas/schema_v1.sql`, migrations, and
  validator/meta paths stay ineligible.
- **Named consumers:** `DIRECT_CURSOR_DELIVERY` guarded merge for later
  product atoms (including Fast Lane after this control lands on `main`) and
  `GITHUB_PR_EXACT_HEAD_CI`.
- **Cheapest falsifier:**
  `schemas/research_memory_projection_v1.sql` with ordinary product paths
  fails `validate_ci_owned_delivery_eligibility`, or
  `schemas/schema_v1.sql` / another non-allowlisted `schemas/*` path is
  admitted.
- **Terminal outcome:** `PROCEED` only if targeted eligibility tests pass,
  focused child commands stay unchanged, exact-head CI is green, and this
  atom's own merge uses `LIVE_PR_HEAD` because it touches
  `scripts/validate_ci.py`.
- **User-visible result:** product research-memory projection DDL no longer
  forces a local full gate; timeout stays 900s; meta/core SQL stays
  tracked-only.
- **Non-goals:** no timeout bump, no LIVE_PR_HEAD CI-consumption bypass for
  product tasks, no Fast Lane behavior change, no TWO_RUNG, no
  pytest-xdist, no skipped clone, no GitHub branch deletion, no merge-phrase
  change, no provider/network/cash.
- **Evidence budget:** offline repository work only; no local full gate
  before PR; no catalog asset registration.
- **Replan trigger:** false admission of core/meta SQL or a validator path,
  a timeout-only "fix", or inability to merge this control via
  `LIVE_PR_HEAD` after green exact-head CI.

## Decision capsule

- `DECISION_DELTA`: keep blanket `schemas/` ineligible; add an exact
  allowlist for product research-memory projection DDL.
- `UNCERTAINTY_REMOVED`: `schemas/research_memory_projection_v1.sql` is
  ci-owned eligible; `schemas/schema_v1.sql` and unnamed `schemas/*` remain
  ineligible. Wall-time fallback is not the chosen repair.
- `CAPABILITY_OR_EVIDENCE`: eligibility tests plus exact-head CI.
- `STOP`: after green exact-head CI and rebuilt `LIVE_PR_HEAD` context;
  do not merge.
- `NEXT`: owner exact phrase, then guarded merge via `LIVE_PR_HEAD`. Then
  integrate this `main` into the open product PR and require a new phrase
  on that new head.
- `SPEC_ROUTE=NONE`

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. This is validation-economy routing, not a
hypothesis-specific code fork. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.

## Authority and non-claims

Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash,
deployment, settings, destructive/history actions and branch deletion are
not authorized. Passing eligibility, CI or merge does not establish
semantic acceptance, canonical `DONE`, alpha or cashflow.
