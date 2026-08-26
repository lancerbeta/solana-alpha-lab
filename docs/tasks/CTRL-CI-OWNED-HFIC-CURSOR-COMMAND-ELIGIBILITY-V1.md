---
task_id: CTRL-CI-OWNED-HFIC-CURSOR-COMMAND-ELIGIBILITY-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-26'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e1c8c3f4f31707fa2ae2de7b161e5954f517fd7a
  expected_upstream: origin/main
  expected_upstream_oid: e1c8c3f4f31707fa2ae2de7b161e5954f517fd7a
  expected_branch: cursor/ctrl-ci-owned-hfic-cursor-command-eligibility
  dirty_mode: ALLOW_REPORTED
objective: Admit the exact HFIC product slash commands to focused ci-owned delivery while keeping blanket .cursor/ and validator paths on tracked-only.
managed_write_set:
  - docs/tasks/CTRL-CI-OWNED-HFIC-CURSOR-COMMAND-ELIGIBILITY-V1.md
  - scripts/validate_ci.py
  - tests/test_ci.py
  - delivery-harness/harness.yaml
  - docs/agent/EXECUTION_ROUTER_PROTOCOL.md
  - catalog/assets/core.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_completion_v1.json
  - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_review_v1.json
  - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_factory_fit_v1.json
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
      - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_completion_v1.json
      - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_review_v1.json
      - docs/evidence/control/a1_ci_owned_hfic_cursor_command_eligibility_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-CI-OWNED-HFIC-CURSOR-COMMAND-ELIGIBILITY-V1

## Task Outcome Brief

- **Owner decision:** HFIC product slash commands are bounded product inventory,
  not harness meta. The measured tracked-only fallback timeout is a symptom of
  the blanket `.cursor/` deny; do not raise the cap.
- **Product outcome:** a product PR that adds only
  `.cursor/commands/hypothesis-forge.md` and
  `.cursor/commands/independent-hypothesis-critic.md` plus otherwise ordinary
  product paths completes guarded-merge primary `--ci-owned-delivery` and
  consumes existing exact-head CI. Other `.cursor/**` and validator/meta paths
  stay ineligible.
- **Named consumers:** `DIRECT_CURSOR_DELIVERY` guarded merge for
  `HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1` and later product atoms with
  named slash commands.
- **Cheapest falsifier:** the two HFIC slash paths with ordinary product paths
  fail `validate_ci_owned_delivery_eligibility`, or another non-allowlisted
  `.cursor/**` path is admitted.
- **Terminal outcome:** `PROCEED` only if targeted eligibility tests pass,
  focused child commands stay unchanged, exact-head CI is green, and this
  atom's own merge uses `LIVE_PR_HEAD` because it touches
  `scripts/validate_ci.py`.
- **User-visible result:** HFIC slash commands no longer force a local full
  gate; timeout stays 900s; meta `.cursor/**` stays tracked-only.
- **Non-goals:** no timeout bump, no LIVE_PR_HEAD CI-consumption bypass for
  product tasks, no Hypothesis Forge behavior change, no provider/network/cash.
- **Evidence budget:** offline repository work only; no local full gate
  before PR; no catalog asset registration.
- **Replan trigger:** false admission of meta `.cursor/**` or a validator path,
  a timeout-only "fix", or inability to merge this control via
  `LIVE_PR_HEAD` after green exact-head CI.

## Decision capsule

- `DECISION_DELTA`: keep blanket `.cursor/` ineligible; add an exact
  allowlist for the two HFIC slash commands.
- `UNCERTAINTY_REMOVED`: the two named slash paths are ci-owned eligible;
  other `.cursor/**` remains ineligible. Wall-time fallback is not the chosen
  repair.
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
