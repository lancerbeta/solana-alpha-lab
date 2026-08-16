---
task_id: TASK-41
task_version: '1.1'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6ad2e5545330fd655c1508da4a49661f9e268cf9
  expected_upstream: origin/main
  expected_upstream_oid: 6ad2e5545330fd655c1508da4a49661f9e268cf9
  expected_branch: cursor/task41-exclusive-raw-noclobber
  dirty_mode: ALLOW_REPORTED
objective: Persist H11 live raw pages with exclusive no-clobber writes.
managed_write_set:
  - docs/tasks/TASK-41-isolated-review-and-raw-noclobber.md
  - src/solana_alpha_lab/storage/exclusive.py
  - tests/test_storage_exclusive_write.py
  - src/solana_alpha_lab/task39_h11_named_mint_gta_clock_capture.py
  - tests/test_task39_rc002_h11_named_mint_gta_clock_capture.py
  - docs/evidence/task41/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task41/a1_delivery_independent_review_v1.json
  - docs/evidence/task41/a1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - GLOBAL_TASK_MODULE_EXTRACTION
  - RUFF_OR_TYPECHECKER_GATE
  - PROVIDER_OR_NETWORK_CALL
  - CATALOG_OR_HARNESS_REWRITE
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task41/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task41/a1_delivery_independent_review_v1.json
      - docs/evidence/task41/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-41 — Exclusive no-clobber H11 raw pages

Merge-deny for `SINGLE_AGENT_REVIEW_FALLBACK` is a separate control PR
(`LIVE_PR_HEAD`). This atom is only the exclusive raw-page writer.

## Task Outcome Brief

- **Owner decision:** H11 live raw pages must not clobber existing bytes.
- **Product outcome:** identical raw page bytes replay; different bytes
  conflict and leave the old file unchanged.
- **Named consumers:** TASK-39 `write_raw_page` and later live-capture atoms.
- **Cheapest falsifier:** `write_raw_page` overwrites different bytes.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** raw evidence stays byte-identical after a retry.
- **Non-goals:** no merge-gate or control-runtime change, no Ruff/type gate,
  no TASK-N domain extraction, no Docker, no provider calls, no rewrite of
  historical review receipts, no TASK-06 storage API export.
- **Evidence budget:** offline repository work only; no local full gate
  before PR.
- **Replan trigger:** catalog/hash cascade, inability to keep TASK-06
  storage API hash stable, or a control-file landing in this write set.

## Decision capsule

- `DECISION_DELTA`: H11 raw pages adopt create-only write with identical replay.
- `UNCERTAINTY_REMOVED`: same run/page cannot silently change bytes.
- `CAPABILITY_OR_EVIDENCE`: exclusive-write tests.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: owner exact phrase, then guarded merge.
- `SPEC_ROUTE=NONE`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_TASK30_OPEN_XB`

## Definition of Done

1. Shared exclusive writer: identical bytes → `REPLAY_IDENTICAL`; different
   bytes → conflict; existing file unchanged.
2. TASK-39 `write_raw_page` uses that writer for body and manifest. Later
   live-capture atoms must call the same helper.
3. The helper is not exported from `storage/__init__.py`.
4. Targeted tests pass. This atom's own review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Raw evidence integrity only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This PR does not change the merge gate.
