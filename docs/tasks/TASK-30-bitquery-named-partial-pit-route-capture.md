---
task_id: TASK-30
task_version: '20.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 828a29af68807809fecb58d1a3b5b8b2dfcd9946
  expected_upstream: origin/main
  expected_upstream_oid: 828a29af68807809fecb58d1a3b5b8b2dfcd9946
  expected_branch: task30/bitquery-pit-capture
  dirty_mode: ALLOW_REPORTED
objective: Execute one bounded Bitquery historical PumpSwap capture that fills the A9 named 96-slot PIT packet without promoting route evidence into H07/H01, execution, PnL or TASK-30 acceptance.
managed_write_set:
  - AGENTS.md
  - delivery-harness/context-map.yaml
  - delivery-harness/policies/solana-alpha-lab.md
  - docs/tasks/TASK-30-bitquery-named-partial-pit-route-capture.md
  - docs/superpowers/plans/2026-08-14-task30-bitquery-named-partial-pit-route-capture.md
  - docs/contracts/task30_bitquery_named_partial_pit_route_capture_contract_v1.md
  - configs/task30_bitquery_named_partial_pit_route_capture_v1.yaml
  - catalog/schemas/task30_bitquery_named_partial_pit_route_capture.schema.json
  - tests/fixtures/task30/bitquery_named_partial_pit_route_capture_v1.json
  - src/solana_alpha_lab/task30_bitquery_named_partial_pit_route_capture.py
  - scripts/run_task30_bitquery_named_partial_pit_route_capture.py
  - tests/test_task30_bitquery_named_partial_pit_route_capture.py
  - docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json
  - docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json
  - docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json
  - docs/reports/task30/bitquery_named_partial_pit_route_capture_readout_v1.md
  - configs/provider_route_capability_registry_v4.yaml
  - catalog/schemas/provider_route_capability_registry_v4.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v4.py
  - tests/test_provider_route_capability_registry_v4.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - registries/decisions_negative_results.yaml
  - local/task30_bitquery_pit_capture/**
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - BITQUERY_TOKEN_MISSING_OR_EXPIRED
  - DNS_TCP_TLS_PREFLIGHT_FAIL
  - HTTP_OR_GRAPHQL_ERROR
  - RESPONSE_BYTES_EXCEED_2000000
  - POOL_MINT_DEX_OR_WINDOW_IDENTITY_DRIFT
  - PROVIDER_REQUEST_COUNT_EXCEEDS_ONE
  - RETRY_OR_FALLBACK_REQUESTED
  - CREDENTIAL_VALUE_EXPOSED
  - CASH_SPEND_REQUESTED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
context_requirements:
  catalog_asset_ids:
    - CONTRACT-T30-NAMED-PARTIAL-CAPTURE-001
    - EVIDENCE-T30-A9-NAMED-PARTIAL-CAPTURE-001
    - EVIDENCE-T30-A19-TERMINAL-ROUTE-DECISION-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004
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
      - docs/evidence/task30/a9_named_partial_pit_route_capture_contract_acceptance_v1.json
      - docs/evidence/task30/a19_terminal_route_decision_acceptance_v1.json
      - docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 — Bitquery named partial PIT route capture

## Task Outcome Brief

- **Owner decision:** determine whether one exact Bitquery route can supply a complete, typed 96-slot market-data panel for `RC001-H07-H01-LIQUIDITY-RETENTION`, and whether TASK-30 may move from route search to data evaluation.
- **Product outcome:** replace repeated provider preparation with one retained query result and an explicit `OBSERVATION | TYPED_GAP` state for every closed 15-minute slot.
- **Named consumer:** `RC001-H07-H01-LIQUIDITY-RETENTION` and the next TASK-30 data-admissibility decision.
- **Cheapest falsifier:** one exact PumpSwap GraphQL query for the frozen pool over one fully closed UTC day; any auth, schema, identity, coverage or retention failure stops without retry or fallback.
- **Terminal outcomes:** `COMPLETE_96_SLOT_MARKET_PANEL`, `PARTIAL_TYPED_GAP_PANEL`, or `ROUTE_UNKNOWN_STOP`.
- **User-visible result:** one Russian readout stating observed/gap counts, exact route evidence, what remains blocked and the next decision.
- **Non-goals:** no fillability, settlement, route quote, execution, PnL, NetReturn, alpha, strategy promotion, wallet, signer, transaction, scheduler, cash spend or canonical TASK-30 acceptance.
- **Evidence budget:** one credential-free DNS/TCP/TLS preflight, at most one credentialed GraphQL request, at most 2,000,000 response bytes, at most 100 Bitquery points, zero cash, zero retry and zero fallback.
- **Replan trigger:** a second provider/route pivot, more than one provider request, untyped missingness, identity drift, credential exposure or inability to retain exact raw bytes plus a tracked normalized panel.

## Frozen route and design contract

`SPEC_ROUTE=DESIGN_SPEC`. The exact provider route is
`BITQUERY-SOLANA-PUMPSWAP-OHLCV-001` at
`https://streaming.bitquery.io/graphql`, authenticated only from local
`BITQUERY_ACCESS_TOKEN`. The query uses `Solana(dataset: archive)` and
`DEXTradeByTokens` with exact pool, PumpSwap program, base mint, WSOL quote,
successful-transaction and closed UTC time filters.

The window is `2026-08-12T00:00:00Z` inclusive through
`2026-08-13T00:00:00Z` exclusive. It is the latest full UTC day with at least
one day of archive-settling margin at task entry. Named notionals are
`10, 25, 50, 100 USD`, but historical OHLCV cannot establish their
fillability; `ROUTE_FEASIBILITY` therefore remains explicitly not established.

Raw response bytes live only under ignored
`local/task30_bitquery_pit_capture/`, with byte count and SHA-256 in the tracked
runtime receipt. The tracked normalized projection retains all 96 slot states.
This is the explicit raw-loss waiver: the historical query is reproducible,
the decision projection is tracked, and raw loss never becomes an invented
observation.

## Definition of Done

1. The Harness context binds this exact contract, branch, base and write set.
2. Offline tests prove exact query filters, one-call cap, secret redaction,
   byte cap, identity rejection and 96 deterministic observation/gap slots.
3. A credential-free preflight passes before the token is read.
4. At most one Bitquery request is retained byte-for-byte outside Git and
   summarized without secret material.
5. The runtime receipt distinguishes complete, partial typed-gap and unknown
   outcomes without turning missingness into zero or no-trade.
6. Provider registry v4 preserves every v3 route semantically and adds exactly
   the observed Bitquery route/result.
7. Catalog, generated navigation, code review, goal/DoD review, architecture
   review, Factory Fit, secret scan, targeted tests, PR and exact-head CI pass.
8. Delivery stops after exact-head CI for the repository-required owner merge
   phrase; merge is not TASK-30 acceptance.

## Authority and non-claims

The owner created a one-day manual Bitquery token for this named task, stored it
locally, confirmed its presence and delegated routine route choice to Codex.
That explicit authority is bounded by the caps above. The credential value may
never enter chat, Git, command arguments, URLs, raw manifests, receipts or logs.

No wallet, signer, transaction, deployment, repository setting, destructive
action, cash spend, retry, fallback or second provider is authorised.

## Implementation checkpoint

- **DECISION_DELTA:** `BITQUERY-SOLANA-PUMPSWAP-OHLCV-001` is observed as
  `ROUTE_UNKNOWN_STOP`; TASK-30 remains `BLOCKED_DATA` and does not switch to
  Bitquery.
- **UNCERTAINTY_REMOVED:** DNS/TCP/TLS reachability and the exact one-request
  authority path passed; provider HTTP/GraphQL cause remains unknown because
  the pre-patch client collapsed `HTTPError` and transport failure.
- **CAPABILITY_OR_EVIDENCE:** one no-retry runtime receipt, a corrected
  evidence-preserving client with regression tests, and append-only provider
  registry v4 preserving all v3 route semantics.
- **STOP:** the one authorized provider request is consumed; no retry,
  fallback or second provider is allowed in this task.
- **NEXT:** deliver the exact candidate through PR and exact-head CI, then stop
  for the repository merge phrase. A new external read requires a fresh owner
  gate and is outside this task.
