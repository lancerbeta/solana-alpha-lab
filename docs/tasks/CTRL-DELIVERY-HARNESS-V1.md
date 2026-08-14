---
task_id: CTRL-DELIVERY-HARNESS-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY, DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e78a08ec7ce5687c89b39fa19d8503ca206c6d9e
  expected_upstream: origin/main
  expected_upstream_oid: e78a08ec7ce5687c89b39fa19d8503ca206c6d9e
  expected_branch: ctrl-delivery-harness-v1
  dirty_mode: ALLOW_REPORTED
objective: Replace active baton routing with one portable Git-native direct Delivery Harness.
managed_write_set:
  path: docs/superpowers/plans/2026-08-13-delivery-harness-v1.md
  heading: Managed write set
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - CONTEXT_DIVERGENCE
  - SECOND_TRUTH_OWNER
context_requirements:
  catalog_asset_ids: [CTRL-DELIVERY-HARNESS-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_evidence_paths:
    - docs/evidence/control/delivery_harness_acceptance_v1.json
  exact_registry_paths: []
---

# CTRL-DELIVERY-HARNESS-V1 — Portable direct delivery harness

## Task Outcome Brief

- **Owner decision:** use Cursor or Codex as equal direct delivery agents over
  one Git-owned project memory and one guarded merge gate.
- **Product outcome:** future bounded work reaches tested code and PR with less
  context waste and fewer routine approval interruptions.
- **Named consumers:** `DIRECT_CODEX_DELIVERY`, `DIRECT_CURSOR_DELIVERY`, goal
  owner and a future repository initialized from the portable profile.
- **Cheapest falsifier:** identical task bytes produce different Cursor/Codex
  context selection, an old baton can regain authority, or a routine delivery
  still requires cloud activation/smoke.
- **Terminal outcome:** `PROCEED` only if deterministic checks, Catalog,
  independent review, tracked-only validation and exact-head CI pass.
- **User-visible result:** one bootstrap prompt, four thin Cursor commands and
  one exact PR/head merge interruption.
- **Non-goals:** no product task selection, provider route, credential, wallet,
  transaction, cash, deployment, plugin installation, remote RAG or UI.
- **Evidence budget:** offline repository work only; one full local delivery
  gate on the final fingerprint; no external product-data calls.
- **Replan trigger:** authority widening, context divergence, repeated
  validation repair, second truth owner or inability to preserve historical
  evidence.

## Scope and invariants

`DELIVERY_HARNESS_V1` owns the route-neutral core, deterministic context
projection, owner-attention v2 policy, portable bootstrap and capability radar.
Cursor and Codex adapters are thin and may not invent task, authority, status or
evidence. `LEGACY_GITHUB_BATON_DORMANT` remains searchable history and cannot
be selected by active rules or commands.

Git is working project memory. Cloud Project Sources and Project Instruction
are `OWNER_MANAGED_OPTIONAL_EXPORT`; the harness never requires replacement,
activation, reminder or smoke and never treats cloud state as execution or DONE
authority.

Both direct agents may perform bounded routine engineering and GitHub delivery.
Both require the exact owner phrase bound to the unchanged PR/head plus every
machine precondition before one ordinary merge. Passing code, PR, CI or merge
does not establish semantic acceptance, canonical DONE, alpha or cashflow.

## Definition of Done

1. Core YAML and receipt contracts validate closed-shape and type-strict.
2. Cursor and Codex resolve equivalent bounded context for identical bytes.
3. Root and always-on Cursor context stay within declared byte budgets.
4. Active Cursor discovery contains no baton rule or command; historical baton
   tooling and receipts remain present and non-authorizing.
5. Owner-attention v2 admits routine work and exact guarded merge only.
6. Task, protocols, ADR-005, skill, tests and evidence are Catalog-resolvable.
7. Capability radar returns `NONE` without a measured trigger and grants no
   install/network/credential/spend authority.
8. Targeted checks, Catalog, generated projections, secret scan, independent
   risk-routed review, tracked-only full gate and exact-head CI pass.
9. Final merge occurs only after exact owner approval for the unchanged PR/head;
   exact main and post-merge CI are read back.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. The acceptance and Factory Fit receipts live
under `docs/evidence/control/`. `PRODUCT_HORIZON_NOW=NONE`: no plugin, remote
memory or generic platform is justified now. `WATCH=FIRST_UNATTENDED_RUNTIME`
for an incident/observability adapter with a named consumer.

## Authority and non-claims

Provider/API/RPC/WSS, credentials, dependency adoption, wallet, signer,
transaction, cash spend, deployment, settings, destructive/history actions,
branch deletion and cloud activation are not authorized. This control task does
not advance or accept TASK-30 and does not select the next product task.
