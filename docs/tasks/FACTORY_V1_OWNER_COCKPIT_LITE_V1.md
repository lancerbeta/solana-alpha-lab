---
task_id: FACTORY_V1_OWNER_COCKPIT_LITE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d3e92705597336929ea3664640549f51b9c91f5e
  expected_upstream: origin/main
  expected_upstream_oid: d3e92705597336929ea3664640549f51b9c91f5e
  expected_branch: cursor/factory-v1-owner-cockpit-lite
  dirty_mode: ALLOW_REPORTED
objective: Make the owner-operable commissioning packet, attention queue, and runtime health visible on the existing localhost Workbench so a normal Factory cycle does not require Git file archaeology, without a new UI package, VPS purchase, or operational-ready claim.
managed_write_set:
  - docs/tasks/FACTORY_V1_OWNER_COCKPIT_LITE_V1.md
  - catalog/schemas/factory_v1_owner_cockpit.schema.json
  - configs/factory_v1_owner_cockpit_v1.yaml
  - src/solana_alpha_lab/factory/cockpit.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - tests/test_factory_v1_owner_cockpit.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_owner_cockpit/a4_factory_v1_cockpit_acceptance_v1.json
  - docs/evidence/factory_v1_owner_cockpit/a4_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_owner_cockpit/a4_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_owner_cockpit/a4_delivery_factory_fit_v1.json
  - docs/reports/factory_v1_owner_cockpit/a4_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - NEW_UI_PACKAGE_ADOPTION
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - LIVE_JUPITER_OR_CREDENTIAL_READ
  - MARKET_CAPTURE_OR_RECAPTURE
  - MOVE_3_OR_NEW_RESEARCH_LADDER
  - PRODUCTION_REGISTRY_SEED
  - SENTRY_OR_COCKPIT_BREADTH
  - TASK35A_PARALLEL_CHAIN
  - EMPTY_ENTERPRISE_SCREENS
  - WALLET_SIGNER_TX_OR_CASH
  - KERNEL_PROVIDER_CALLS_TRUE
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
    - CONFIG-FACTORY-V1-PRODUCT-KERNEL-001
    - MODULE-FACTORY-V1-WORKBENCH-001
    - EVIDENCE-FACTORY-V1-COMMISSIONING-ACCEPTANCE-001
    - EVIDENCE-FACTORY-V1-PRODUCTION-LITE-RUNTIME-ACCEPTANCE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_v1_owner_cockpit/a4_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_OWNER_COCKPIT_LITE_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=PATCH`

ATOM 3 is on `main`. Named NEXT was real VPS or ATOM 4 Cockpit.
Buying a VPS is still `LATER_EXTERNAL_AUTHORITY` and would be
preparatory-only. Full ARCH-INTENT-005 section 8 IA plus a new UI
package would explode scope and trip `ui_framework_selection: false`.

PATCH: wrap the existing stdlib Workbench into an owner-operable
Cockpit-lite. Visible nav is HOME / RESEARCH / SYSTEM. MARKET,
OPERATIONS, and ECONOMICS stay hidden, not empty enterprise screens.

Owner trigger: `го дальше` plus choose ATOM 4 or better, write PRD+SSD
and execute. That is not a Jupiter phrase, not a VPS purchase, and not
`FACTORY_V1_OPERATIONAL_READY`.

`strongest_rejected_alternative`: actual VPS host.
`why_rejected_now`: cash/deploy gate; does not prove owner visibility.

## PRD-lite

- **Outcome that must become true:** the owner can read QUESTION,
  ESTIMAND, POPULATION, DATA, RESULT, UNCERTAINTY, ROBUSTNESS, FAILURE,
  DECISION, NEXT, plus attention items (`WHY_NOW / IMPACT / EVIDENCE /
  NEXT_SAFE_ACTION`) and runtime health, from localhost Workbench without
  opening Git files.
- **Why now:** commissioning packet and runtime proof exist on `main`,
  but Workbench still dumps a flat projection. Owner operability in the
  readiness gate is the cheapest remaining in-scope falsifier.
- **Downstream consumer:** the owner operating Factory after ATOM 2/3
  without agent mediation. Later VPS host remains a later exact gate.
- **Current gap:** `git_archaeology_required` is hardcoded false; packet
  fields and attention queue are not first-class; full Cockpit IA is not
  implemented and must not be faked.
- **Success observable:** isolated tests plus one owner readout showing
  `OWNER_COCKPIT_LITE_OPERABILITY_PASS` with operational-ready still
  false and backup still `EXPLICIT_UNKNOWN`.
- **Invalidation / cheapest falsifier:** missing Git evidence still
  reports archaeology false; HEALTHY from process_alive; empty MARKET
  / OPERATIONS / ECONOMICS screens; new UI package; VPS purchase;
  operational-ready claim; Jupiter recapture.
- **Non-goals:** `FACTORY_V1_OPERATIONAL_READY`, full section 8 IA,
  NiceGUI/Streamlit/FastAPI/React, Sentry, Drive backup, VPS, MOVE 3,
  live Jupiter, production registry seed, kernel `provider_calls: true`.

Frozen cockpit hypothesis (product, not market):

- ID: `HYP-FACTORY-V1-OWNER-COCKPIT-LITE-V1`
- Experiment: `EXP-FACTORY-V1-OWNER-COCKPIT-LITE-001`
- Capability: `CAP-FACTORY-V1-OWNER-COCKPIT-LITE-001`
- Product question: can the owner operate the commissioning cycle and
  runtime health from Workbench without Git archaeology?
- Estimand: presence of the owner packet and attention fields on the
  localhost projection; not PnL.
- Population: one operator, existing stdlib Workbench, Git-bound
  ATOM 2/3 receipts.

## SSD-lite

- **Baseline truth:** `origin/main`
  `d3e92705597336929ea3664640549f51b9c91f5e`. ATOM 1 golden PASS.
  ATOM 2 commissioning PASS. ATOM 3 runtime proof PASS. MOVE 3 not
  earned. Production registries empty. Kernel `provider_calls: false`.
  Purchase later. UI package adoption false.
- **Design:** ADOPT existing FactoryApplication, read model, Workbench,
  commissioning Git receipts, runtime health projection. WRAP them with
  a cockpit projection and HOME/RESEARCH/SYSTEM pages. FORK nothing in
  capture. BUILD no UI package and no second truth store.
- **Invariants:** Git/Catalog/receipts remain scientific truth; UI owns
  nothing; process_alive alone is not healthy; backup stays
  `EXPLICIT_UNKNOWN`; localhost bind only; no `.env`; no provider calls;
  `git_archaeology_required` is true iff required evidence is missing.
- **Affected surfaces:** cockpit config+schema, cockpit projector,
  read-model archaeology honesty, Workbench navigation/pages.
  Kernel schema stays ATOM 1. Runtime and commissioning receipts stay
  hash-bound.
- **Failure modes:** `GIT_ARCHAEOLOGY_REQUIRED` when spec coverage is
  missing; hidden nav rendered as empty screens; command buttons implying
  Jupiter/deploy authority.
- **Validation:** fail-closed tests with zero network; packet fields on
  `/` and `/research`; runtime strings remain on `/`; hidden IA absent;
  missing acceptance flips archaeology; no HEALTHY; no operational-ready
  string; pyproject gains no UI extra.
- **Rollback of this atom:** revert the branch. SQLite under `local/` is
  not Git truth.

## Decision capsule

- `DECISION_DELTA`: treat ATOM 4 as Cockpit-lite on the existing
  Workbench, not VPS purchase and not full owner-experience IA.
- `UNCERTAINTY_REMOVED`: whether the owner can see the commissioning
  packet, attention, and runtime health without Git archaeology.
- `CAPABILITY_OR_EVIDENCE`: `CAP-FACTORY-V1-OWNER-COCKPIT-LITE-001`,
  cockpit projection, Workbench HOME/RESEARCH/SYSTEM, owner packet.
- `STOP`: before any UI package, VPS, Jupiter, or operational-ready
  claim. After proofs, at exact-head CI for the merge phrase.
- `NEXT`: real VPS host or Drive backup only under a later exact owner
  gate; not MOVE 3; not Sentry.
- `ADOPTION_ROUTE=WRAP_EXISTING_STDLIB_WORKBENCH`
- `REPLAN_TRIGGER`: second consecutive preparatory-only merge; cheapest
  falsifier cannot run; UI-package/VPS pivot; Cockpit breadth without a
  named owner-operability gap; evidence/time budget exceeded.

## Definition of Done

1. Cockpit config+schema freeze visible HOME/RESEARCH/SYSTEM, hidden
   MARKET/OPERATIONS/ECONOMICS, packet fields, attention fields, and
   `ui_package_adoption: false`.
2. Read model sets `git_archaeology_required` from missing Git coverage,
   not a hardcoded false.
3. Workbench HOME shows attention, packet, runtime health summary, and
   existing copy-blocks/commands. RESEARCH shows the packet. SYSTEM
   shows runtime. Hidden IA is not rendered.
4. Missing commissioning acceptance makes archaeology true and is
   visible without claiming HEALTHY or operational-ready.
5. No production registry seed. No operational-ready claim. No VPS.
   No new UI package.

## Merge evidence

`exact_role_paths.DELIVERY_EVIDENCE` at merge must list exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/factory_v1_owner_cockpit/a4_delivery_completion_evidence_v1.json`
