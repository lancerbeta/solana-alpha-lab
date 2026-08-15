---
task_id: CTRL-AUTONOMOUS-DELIVERY-SKILL-V1
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
  expected_branch: cursor/autonomous-delivery-skill
  dirty_mode: ALLOW_REPORTED
objective: Turn owner continue/what-next intents into one project skill that selects and delivers one bounded atom on Delivery Harness without a second control plane.
managed_write_set:
  - docs/tasks/CTRL-AUTONOMOUS-DELIVERY-SKILL-V1.md
  - .agents/skills/autonomous-delivery/SKILL.md
  - .agents/skills/autonomous-delivery/references/product-system-contract.md
  - .agents/skills/autonomous-delivery/references/roadmap-challenge.md
  - AGENTS.md
  - catalog/assets/core.yaml
  - tests/test_autonomous_delivery_skill.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - SECOND_CONTROL_PLANE
  - HARNESS_PROCEDURE_DUPLICATION
  - NUMERIC_TASK_SUCCESSION
  - PLUGIN_MCP_OR_NEW_DEPENDENCY
  - PROVIDER_OR_NETWORK_CALL
  - LOCAL_FULL_GATE_BEFORE_PR
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

# CTRL-AUTONOMOUS-DELIVERY-SKILL-V1

## Task Outcome Brief

- **Owner decision:** repeatable continue/what-next intents become a native
  project Cursor skill that restores truth, challenges the plan, and delivers
  one bounded atom to the exact merge gate.
- **Product outcome:** the owner can say `го дальше` / `what next` and get
  one executed atom instead of a menu, a numeric next TASK, or a strategy
  essay.
- **Named consumers:** `DIRECT_CURSOR_DELIVERY`, goal owner, later continue
  intents in this repository.
- **Cheapest falsifier:** the skill folder/frontmatter mismatch, a second
  control plane, copied harness procedures, or a model that would take the
  next `TASK-XX` by number.
- **Terminal outcome:** `PROCEED` only if targeted skill tests pass, write set
  is exact, exact-head CI is green, and merge waits for the owner phrase.
- **User-visible result:** `/autonomous-delivery` plus automatic relevance;
  a few-line `AGENTS.md` pointer; no plugin/MCP/automation.
- **Non-goals:** no replacement of Delivery Harness; no Catalog registration;
  no `validate_ci.py` / `test_ci.py` / domain-policy / execution-router edits;
  no provider/network/cash; no merge in this atom.
- **Evidence budget:** offline repository work; targeted tests only; no local
  full gate before PR.
- **Replan trigger:** authority widening, a second truth owner, or inability
  to keep the skill as a thin overlay.

## Decision capsule

- `DECISION_DELTA`: add `autonomous-delivery` as a receding-horizon overlay
  that ADOPTs `.agents/skills/delivery-harness/SKILL.md`.
- `UNCERTAINTY_REMOVED`: continue intents have one project owner; roadmap is
  revisable (`KEEP|PATCH|REORDER|REBASE`); one atom; stop only at real gates.
- `CAPABILITY_OR_EVIDENCE`: skill + two phase references + AGENTS pointer +
  targeted tests.
- `STOP`: after green exact-head CI and `LIVE_PR_HEAD` context; do not merge.
- `NEXT`: owner exact phrase, then guarded merge.
- `SPEC_ROUTE=NONE`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` for this control overlay; later
  ordinary continue atoms stay `LUNA_MAX` unless a material contract/PIT/
  security question appears.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW` because this is control-plane routing of
agent delivery. It does not change estimand, data contracts, or cashflow
authority. `PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.

## Authority and non-claims

Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash,
deployment, settings, destructive/history actions and branch deletion are
not authorized. Passing tests, CI or merge do not establish semantic
acceptance, canonical `DONE`, alpha or cashflow. This skill does not widen
harness-gated authority.
