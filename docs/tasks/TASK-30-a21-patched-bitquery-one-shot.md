---
task_id: TASK-30
task_version: '21.0'
status: IN_PROGRESS
as_of: '2026-08-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3b532d6ad4a875837bee061ff2e7832e86344fdb
  expected_upstream: origin/main
  expected_upstream_oid: 3b532d6ad4a875837bee061ff2e7832e86344fdb
  expected_branch: task30/a21-patched-bitquery-one-shot
  dirty_mode: ALLOW_REPORTED
objective: Execute one patched Bitquery historical PumpSwap capture on the already-merged evidence-retaining client without retrying A20 or promoting TASK-30.
managed_write_set:
  - docs/tasks/TASK-30-a21-patched-bitquery-one-shot.md
  - docs/contracts/task30_a21_patched_bitquery_one_shot_contract_v1.md
  - configs/task30_a21_patched_bitquery_one_shot_v1.yaml
  - catalog/schemas/task30_a21_patched_bitquery_one_shot.schema.json
  - tests/test_task30_a21_patched_bitquery_one_shot.py
  - scripts/run_task30_a21_patched_bitquery_one_shot.py
  - docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json
  - docs/evidence/task30/a21_patched_bitquery_one_shot_acceptance_v1.json
  - docs/reports/task30/a21_patched_bitquery_one_shot_readout_v1.md
  - docs/superpowers/plans/2026-08-14-task30-a21-patched-bitquery-one-shot.md
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - local/task30_a21_bitquery_one_shot/**
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
  - A20_RECEIPT_MUTATION_ATTEMPTED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
  - RETRY_OR_FALLBACK_REQUESTED
  - CREDENTIAL_VALUE_EXPOSED
  - CASH_SPEND_REQUESTED
  - PROVIDER_REQUEST_COUNT_EXCEEDS_ONE
context_requirements:
  catalog_asset_ids:
    - CONTRACT-T30-A21-PATCHED-BITQUERY-ONE-SHOT-001
    - CONTRACT-T30-A20-BITQUERY-PIT-CAPTURE-001
    - EVIDENCE-T30-A20-BITQUERY-PIT-CAPTURE-001
    - EVIDENCE-T30-A20P-BITQUERY-PIT-CAPTURE-001
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
      - docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json
      - docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json
      - docs/evidence/task30/a19_terminal_route_decision_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A21 — Patched Bitquery one-shot

## Task Outcome Brief

- **Owner decision:** keep `RC001-H07-H01-LIQUIDITY-RETENTION` as the consumer and run one patched Bitquery request that can retain HTTP evidence A20 lost.
- **Product outcome:** replace an uninformative `TRANSPORT_ERROR` with a same-route observation whose HTTP/GraphQL cause is retained, without retrying A20.
- **Named consumer:** `RC001-H07-H01-LIQUIDITY-RETENTION`.
- **Cheapest falsifier:** one patched POST for the frozen pool and UTC day; HTTP status must be retained on `HTTPError`.
- **Terminal outcomes:** `COMPLETE_96_SLOT_MARKET_PANEL`, `PARTIAL_TYPED_GAP_PANEL` or `ROUTE_UNKNOWN_STOP`.
- **User-visible result:** one A21 runtime receipt with retained HTTP/GraphQL evidence and unchanged A20 bytes.
- **Non-goals:** no retry, fallback, second provider, A20 mutation, fillability, execution, PnL, NetReturn, alpha or TASK-30 acceptance.
- **Evidence budget:** one credential-free DNS/TCP/TLS preflight, at most one credentialed GraphQL request, at most 2,000,000 response bytes, zero retry and zero fallback.
- **Replan trigger:** a second route pivot, any attempt to rewrite A20 receipts, more than one provider request, or credential exposure.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=NONE`

`OWNER_CAPTURE_PHRASE=AUTHORIZED_2026_08_14`

## Scope

Reuse A20 design, pool, window and patched client on
`3b532d6ad4a875837bee061ff2e7832e86344fdb`. Add only A21 paths. Do not edit
`scripts/run_task30_bitquery_named_partial_pit_route_capture.py` or A20
receipts in this atom.

## Definition of Done

1. Harness context binds this contract, branch and write set.
2. Closed tests prove same-route identity, authorized one-shot, HTTP-evidence
   obligation, unauthorized refusal and A20 path immutability.
3. Catalog lists the A21 contract/config/schema/test/script assets.
4. One credential-free preflight and at most one patched POST are recorded on
   A21 paths only. A20 receipts and script bytes are unchanged.
5. The runtime receipt retains HTTP status on `HTTPError`. TASK-30 stays
   `BLOCKED_DATA` unless a complete 96-slot panel is observed, and even then
   is not accepted as PIT/H07/H01/NetReturn evidence.

## Authority and next

The owner authorized one patched Bitquery POST. Zero retry, zero fallback,
zero second provider, zero cash, zero A20 mutation. After the one-shot, stop
and report the terminal outcome. Do not start TASK-29, TASK-31 or TASK-34A.
