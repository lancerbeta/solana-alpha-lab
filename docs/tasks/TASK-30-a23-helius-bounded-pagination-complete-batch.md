---
task_id: TASK-30
task_version: '23.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 8f1c957d6378d693cc34f8b0f3f328bd339ed3be
  expected_upstream: origin/main
  expected_upstream_oid: 8f1c957d6378d693cc34f8b0f3f328bd339ed3be
  expected_branch: codex/task30-a23-helius-bounded-pagination
  dirty_mode: ALLOW_REPORTED
objective: Reuse the immutable A22 Helius first page, make at most two bounded continuation requests, and decide whether the frozen raw transaction batch is complete without promoting TASK-30.
managed_write_set:
  - docs/tasks/TASK-30-a23-helius-bounded-pagination-complete-batch.md
  - docs/superpowers/plans/2026-08-15-task30-a23-helius-bounded-pagination.md
  - docs/contracts/task30_a23_helius_bounded_pagination_complete_batch_contract_v1.md
  - configs/task30_a23_helius_bounded_pagination_complete_batch_v1.yaml
  - catalog/schemas/task30_a23_helius_bounded_pagination_complete_batch.schema.json
  - tests/fixtures/task30/helius_bounded_pagination_v1.json
  - src/solana_alpha_lab/task30_helius_get_transactions_for_address.py
  - src/solana_alpha_lab/task30_helius_bounded_pagination.py
  - scripts/run_task30_a23_helius_bounded_pagination.py
  - tests/test_task30_a22_helius_get_transactions_for_address.py
  - tests/test_task30_a23_helius_bounded_pagination.py
  - docs/evidence/task30/a23_helius_bounded_pagination_runtime_receipt_v1.json
  - docs/evidence/task30/a23_helius_bounded_pagination_acceptance_v1.json
  - docs/evidence/task30/a23_provider_route_capability_registry_acceptance_v1.json
  - docs/reports/task30/a23_helius_bounded_pagination_readout_v1.md
  - configs/provider_route_capability_registry_v6.yaml
  - catalog/schemas/provider_route_capability_registry_v6.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v6.py
  - tests/test_provider_route_capability_registry_v6.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - registries/decisions_negative_results.yaml
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - docs/evidence/task30/a23_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a23_delivery_independent_review_v1.json
  - docs/evidence/task30/a23_delivery_factory_fit_v1.json
  - local/task30_a23_helius_bounded_pagination/**
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - A22_FIRST_PAGE_IDENTITY_DRIFT
  - HELIUS_API_KEY_MISSING_OR_EXPIRED
  - DNS_TCP_TLS_PREFLIGHT_FAIL
  - PROVIDER_METHOD_OR_PLAN_ERROR
  - RESPONSE_PAGE_BYTES_EXCEED_25000000
  - RESPONSE_TOTAL_NEW_BYTES_EXCEED_50000000
  - PAGE_CREDITS_UPPER_BOUND_EXCEEDS_100
  - TOTAL_CREDITS_UPPER_BOUND_EXCEEDS_200
  - PAGINATION_CURSOR_MISSING_MALFORMED_OR_REPEATED
  - RESPONSE_SCHEMA_OR_GLOBAL_ORDER_DRIFT
  - DUPLICATE_SIGNATURE_OR_TRANSACTION_KEY
  - PROVIDER_REQUEST_COUNT_EXCEEDS_TWO
  - RETRY_REDIRECT_OR_FALLBACK_REQUESTED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
  - CREDENTIAL_OR_RAW_CURSOR_VALUE_EXPOSED
  - CASH_SPEND_OR_PLAN_SETTING_CHANGE_REQUESTED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T30-A22-HELIUS-GTA-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-005
    - CONTRACT-T30-H07-H01-DATA-CONTRACT-GATE-001
  l2_roles: [EXTERNAL_ROUTE_KNOWLEDGE, DELIVERY_EVIDENCE, ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v5.yaml
    ARCHITECTURE_DECISIONS:
      - docs/decisions/ADR-002-mvp-stack.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json
      - docs/evidence/task30/a22_helius_get_transactions_for_address_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A23 — Helius bounded pagination complete batch

## Task Outcome Brief

- **Owner decision:** determine whether the exact A22 Helius batch becomes complete within two continuation pages and a 200-credit / 50 MB new-data ceiling.
- **Product outcome:** obtain a complete raw-batch candidate for `RC001-H07-H01-LIQUIDITY-RETENTION`, or close this bounded Helius historical route without another provider suffix atom.
- **Cheapest falsifier:** verify retained A22 page 0 by exact SHA-256, then follow its opaque cursor sequentially until null or two continuation calls are consumed.
- **Terminal outcomes:** `COMPLETE_RAW_BATCH_CANDIDATE`, `BOUNDED_PAGINATION_INCOMPLETE_STOP`, `A22_BINDING_DRIFT`, `PROVIDER_TYPED_FAILURE`, or `TRANSPORT_OR_VALIDATION_STOP`.
- **Evidence budget:** one credential-free DNS/TCP/TLS preflight, one local key read, at most two sequential Helius POSTs, at most 100 credits and 25,000,000 bytes per new page, at most 200 credits and 50,000,000 bytes total new data, 30-second timeout per call and zero purchase.
- **Non-goals:** no refetch of A22 page 0, retry, redirect, fallback, second provider, plan or autoscaling change, purchase, PIT-admissibility claim, OHLCV, H07/H01 result, alpha, strategy promotion or TASK-30 acceptance.
- **Replan trigger:** a non-null cursor after call 2 or any typed stop closes this exact bounded capture and returns to product selection; it does not authorize A24.

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=DESIGN_SPEC`

`ADOPTION_ROUTE=WRAP_A22_TESTED_CLIENT`

`OWNER_CAPTURE_PHRASE=OK T30-A23 HELIUS_BOUNDED_PAGINATION_COMPLETE_BATCH`

## Frozen pagination contract

The immutable first page is the retained A22 raw response under
`local/task30_a22_helius_get_transactions_for_address/`, bound by SHA-256
`7244a4c049c7ebe5f77d6136513d402c9af568dd0ccabb3a842160ab61a72bcc`,
520 results and cursor SHA-256
`8ef7a4d174cf6846b11c5e57d1127edea0575fb66ce06fefc68997ebe55ab2ec`.
It is read-only and is never refetched.

Each continuation keeps the A22 pool, closed UTC window, finalized successful
transactions, chronological ordering, full transaction details, maximum
transaction version 0, no token-account expansion and limit 1,000. Only the
opaque `paginationToken` and request id vary. Raw cursor values live only in
process memory or ignored raw response bytes; tracked evidence stores hashes.

Global validation requires strict increasing `(slot, transactionIndex)` keys,
nondecreasing block time, unique transaction keys and signatures, exact
pool/window identity and full successful transaction/meta objects across page
0 and every continuation page.

## Definition of Done

1. Delivery Harness context binds this exact task, branch, base and write set.
2. RED/GREEN tests prove immutable page-0 binding, sequential pagination,
   global dedup/order validation, early completion and every page/atom cap.
3. One preflight precedes exactly one credential read; zero to two continuation
   pages are retained create-only outside Git without retry or redirect.
4. The terminal outcome and exact hashes/counts/credit upper bounds are tracked
   without a credential or raw cursor value.
5. Provider registry v6 appends the observed A23 result while preserving v5
   semantics; Catalog/generated navigation and decision evidence agree.
6. Code, goal/DoD, architecture and Factory Fit review plus proportional tests,
   schema/catalog validation, diff/write-set and secret checks pass.
7. `TASK-30` remains `BLOCKED_DATA`; even a complete raw batch is only input to
   a separately authorized data-admissibility decision.
8. Delivery stops after exact-head CI for the exact repository-required owner
   merge phrase; merge is not semantic acceptance.

## Authority and non-claims

The owner authorized only this exact bounded continuation. Existing account
credits may be consumed up to the stated cap; no purchase, billing/plan setting,
autoscaling change, second provider, deployment, wallet, signer, transaction,
repository setting or destructive action is authorized.

## Implementation checkpoint

- **DECISION_DELTA:** the immutable A22 page plus one 93-byte continuation form
  a complete raw-batch candidate: continuation returned HTTP 200, zero rows and
  a null cursor. A second authorized call was not spent.
- **UNCERTAINTY_REMOVED:** full historical transaction coverage for the exact
  frozen pool/day is no longer the current blocker. PIT-safe transformation and
  data admissibility for the named H07/H01 consumer remain unproven.
- **CAPABILITY_OR_EVIDENCE:** 520 globally unique ordered full transactions,
  exact retained page hashes, one preflight, one credential read, one provider
  request, 10-credit upper bound, registry v6 and a fail-closed bounded runner.
- **STOP:** A23 makes no more provider calls and authorizes no retry, fallback,
  second provider, purchase, plan/autoscaling change or TASK-30 promotion.
- **NEXT:** deliver this candidate through PR and exact-head CI. After merge,
  the owner decides whether RC001 still justifies a separately authorized
  raw-to-PIT data-admissibility atom; do not create A24 automatically.
