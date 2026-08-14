---
task_id: TASK-30
task_version: '22.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4073f5663a7e0c05cbce369668a37799d06d32cb
  expected_upstream: origin/main
  expected_upstream_oid: 4073f5663a7e0c05cbce369668a37799d06d32cb
  expected_branch: codex/task30-a22-helius-gta-one-shot
  dirty_mode: ALLOW_REPORTED
objective: Execute one bounded Helius getTransactionsForAddress request for the frozen A20 pool and UTC window, retain the full transaction batch, and decide route fit without promoting TASK-30.
managed_write_set:
  - docs/tasks/TASK-30-a22-helius-get-transactions-for-address-one-shot.md
  - docs/contracts/task30_a22_helius_get_transactions_for_address_one_shot_contract_v1.md
  - configs/task30_a22_helius_get_transactions_for_address_one_shot_v1.yaml
  - catalog/schemas/task30_a22_helius_get_transactions_for_address_one_shot.schema.json
  - tests/fixtures/task30/helius_get_transactions_for_address_v1.json
  - src/solana_alpha_lab/task30_helius_get_transactions_for_address.py
  - scripts/run_task30_a22_helius_get_transactions_for_address.py
  - tests/test_task30_a22_helius_get_transactions_for_address.py
  - docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json
  - docs/evidence/task30/a22_helius_get_transactions_for_address_acceptance_v1.json
  - docs/evidence/task30/a22_provider_route_capability_registry_acceptance_v1.json
  - docs/reports/task30/a22_helius_get_transactions_for_address_readout_v1.md
  - configs/provider_route_capability_registry_v5.yaml
  - catalog/schemas/provider_route_capability_registry_v5.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v5.py
  - tests/test_provider_route_capability_registry_v5.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - registries/decisions_negative_results.yaml
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - docs/evidence/task30/a22_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a22_delivery_independent_review_v1.json
  - docs/evidence/task30/a22_delivery_factory_fit_v1.json
  - local/task30_a22_helius_get_transactions_for_address/**
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - HELIUS_API_KEY_MISSING_OR_EXPIRED
  - DNS_TCP_TLS_PREFLIGHT_FAIL
  - PROVIDER_METHOD_OR_PLAN_ERROR
  - RESPONSE_BYTES_EXCEED_25000000
  - RESULT_COUNT_EQUALS_OR_EXCEEDS_1000
  - PAGINATION_TOKEN_PRESENT
  - POOL_OR_WINDOW_IDENTITY_DRIFT
  - RESPONSE_SCHEMA_OR_ORDER_DRIFT
  - PROVIDER_REQUEST_COUNT_EXCEEDS_ONE
  - RETRY_OR_FALLBACK_REQUESTED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
  - CREDENTIAL_VALUE_EXPOSED
  - CASH_SPEND_REQUESTED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T30-A21-PATCHED-BITQUERY-ONE-SHOT-001
    - CONTRACT-T30-A20-BITQUERY-PIT-CAPTURE-001
    - EVIDENCE-T30-A20-BITQUERY-PIT-CAPTURE-001
    - EVIDENCE-T30-A20P-BITQUERY-PIT-CAPTURE-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004
    - CONTRACT-T30-H07-H01-DATA-CONTRACT-GATE-001
  l2_roles: [EXTERNAL_ROUTE_KNOWLEDGE, DELIVERY_EVIDENCE, ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v4.yaml
    ARCHITECTURE_DECISIONS:
      - docs/decisions/ADR-002-mvp-stack.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a21_delivery_completion_evidence_v1.json
      - docs/evidence/task30/a21_patched_bitquery_one_shot_acceptance_v1.json
      - docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json
      - docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A22 — Helius getTransactionsForAddress one-shot

## Task Outcome Brief

- **Owner decision:** determine whether the already available Helius access can return one complete, reproducible raw transaction batch for the frozen PumpSwap pool and UTC day without a purchase.
- **Product outcome:** close the current provider decision gap with observed full-transaction evidence, not another adapter-only artifact.
- **Named consumer:** `RC001-H07-H01-LIQUIDITY-RETENTION` and the next TASK-30 data-admissibility decision.
- **Cheapest falsifier:** one `getTransactionsForAddress` POST with the exact pool, finalized successful-transaction filter, closed UTC window, chronological order and limit 1,000.
- **Terminal outcomes:** `BATCH_OBSERVED_LT_1000`, `ZERO_RESULT_TYPED_GAP`, `TRUNCATED_AT_1000_STOP`, `PAGINATION_REQUIRED_STOP`, `PROVIDER_TYPED_FAILURE`, or `TRANSPORT_OR_COVERAGE_UNKNOWN`.
- **User-visible result:** one Russian readout with request count, HTTP/JSON-RPC terminal state, transaction count, exact raw-byte digest, route-fit decision and remaining TASK-30 block.
- **Non-goals:** no retry, pagination, fallback, second provider, OHLCV construction, fillability, route feasibility, settlement, execution, PnL, NetReturn, alpha, strategy promotion or TASK-30 acceptance.
- **Evidence budget:** one credential-free DNS/TCP/TLS preflight, one local key read, at most one provider POST, at most 1,000 full transactions, at most 100 Helius credits, at most 25,000,000 response bytes, 30-second timeout and zero cash.
- **Replan trigger:** any terminal stop closes this route and returns the owner to product/hypothesis selection; it does not authorize another suffix provider pivot.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=DESIGN_SPEC`

`OWNER_CAPTURE_PHRASE=OK T30-A22 HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT`

## Frozen route and evidence contract

The exact route is `HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001` at the
official Helius mainnet RPC endpoint. Authentication is read only from local
`HELIUS_API_KEY` after credential-free preflight; the value may never enter
arguments, logs, receipts, Git or chat.

The address is pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`. The closed
window is `2026-08-12T00:00:00Z` inclusive through `2026-08-13T00:00:00Z`
exclusive, equivalently block times `[1786492800, 1786579200)`. The request is
finalized, successful-only, chronological, `transactionDetails=full`,
`maxSupportedTransactionVersion=0`, `tokenAccounts=none`, and `limit=1000`.

Exact raw response bytes live only under ignored
`local/task30_a22_helius_get_transactions_for_address/`. The tracked runtime
receipt records byte count and SHA-256 but no credential or endpoint query.
A result count of exactly 1,000 is possible truncation and stops without a
pagination request. A count below 1,000 is route-fit evidence only; it is not
yet an admissible 96-slot market panel or H07/H01 evidence.

## Definition of Done

1. Harness context binds this exact contract, route, base, branch and write set.
2. RED/GREEN tests prove exact filters, one-call cap, no redirects/retry,
   secret redaction, byte cap, schema/order/window validation and terminal
   outcome classification.
3. Credential-free DNS/TCP/TLS preflight passes before the local key is read.
4. At most one provider POST is retained byte-for-byte outside Git and
   summarized without secret material.
5. Provider registry v5 preserves all v4 route semantics and appends exactly
   the observed Helius route/result.
6. Catalog, generated navigation, code review, goal/DoD review, architecture
   review, Factory Fit, secret scan, targeted tests, PR and exact-head CI pass.
7. TASK-30 remains `BLOCKED_DATA`; success only routes to a later explicit
   data-admissibility atom, while any stop returns to product selection.
8. Delivery stops after exact-head CI for the exact repository-required owner
   merge phrase; merge is not TASK-30 acceptance.

## Authority and non-claims

The owner explicitly authorized this single Helius call. No pagination, retry,
fallback, second provider, package adoption, cash spend, wallet, signer,
transaction, deployment, repository setting or destructive action is
authorized.

## Implementation checkpoint

- **DECISION_DELTA:** the existing Helius route is technically live, but the
  one-shot completeness criterion failed: one HTTP 200 response returned 520
  full transactions plus `paginationToken`.
- **UNCERTAINTY_REMOVED:** Helius can return full successful pool transactions
  for the exact historical window without a purchase in this atom; whether the
  complete batch is admissible remains unknown because pagination was forbidden.
- **CAPABILITY_OR_EVIDENCE:** one exact 9,012,030-byte response retained outside
  Git, tracked SHA-256, fail-closed parser, no-retry runner and append-only
  provider registry v5.
- **STOP:** the only authorized provider request is consumed. No pagination,
  retry, fallback, second provider or cash action is allowed.
- **NEXT:** deliver this candidate through PR and exact-head CI. After merge,
  the owner decides whether `RC001-H07-H01-LIQUIDITY-RETENTION` still justifies
  a separately authorized bounded paginated capture; do not create A23
  automatically.
