---
task_id: RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a81568ea17d9615e4e2cde6d57852bde6b8bb8c0
  expected_upstream: origin/main
  expected_upstream_oid: a81568ea17d9615e4e2cde6d57852bde6b8bb8c0
  expected_branch: cursor/rc002-h11-bounded-gettransaction-create
  dirty_mode: ALLOW_REPORTED
objective: Perform one keyless standard-RPC getTransaction of the retained A4 Create signature and compare its Create Program-data length to GTA 195.
managed_write_set:
  - docs/tasks/RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1.md
  - src/solana_alpha_lab/rc002_h11_bounded_gettransaction_create.py
  - tests/test_rc002_h11_bounded_gettransaction_create.py
  - scripts/run_rc002_h11_bounded_gettransaction_create.py
  - tests/fixtures/rc002_h11/gettransaction_create_same_195_v1.json
  - tests/fixtures/rc002_h11/gettransaction_create_null_v1.json
  - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_bounded_gettransaction_create_acceptance_v1.json
  - docs/reports/rc002_h11_bounded_gettransaction_create/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_factory_fit_v1.json
external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - CREDENTIAL_READ
  - HELIUS_OR_GTA_CALL
  - RETRY_OR_FALLBACK
  - CATALOG_OR_HARNESS_REWRITE
  - REGISTRY_REWRITE
  - RC001_FREEZE_MUTATED
  - HOLDOUT_CONSUMED
  - LIVE_PIT_OR_EXECUTION_CLAIM
  - UNBOUNDED_PUMP_PROGRAM_GTA
  - HISTORICAL_RECEIPT_REWRITE
  - PINNED_PUMP_DECODER_MUTATION
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v3.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_create_without_virtual_quote_acceptance_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_bounded_gettransaction_create_acceptance_v1.json
      - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1

One keyless standard-RPC `getTransaction` of the retained A4 Create
signature. Pinned TASK-08 decoder bytes stay immutable. TASK-40/39 and
previous H11 science receipts stay immutable. Registry is not rewritten.

## Task Outcome Brief

- **Owner decision:** open one bounded `getTransaction` after offline
  two-field Create mask still failed (`CREATE_STILL_TRUNCATED_NEED_GETTRANSACTION`).
- **Product outcome:** one terminal comparing getTransaction Create
  Program-data length to GTA 195 under candidate
  `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES`.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** getTransaction returns the same 195 still
  truncated, a longer body, null, or a typed transport/provider failure.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one enum.
- **Non-goals:** no Helius, no `getTransactionsForAddress`, no Pump-program
  GTA, no credential, no retry/fallback, no registry/catalog rewrite, no
  pinned decoder mutation, no TASK-40/39 receipt mutation, no live PIT.
- **Evidence budget:** one POST, max 2_000_000 response bytes; raw A4
  outside Git; no local full gate before PR.
- **Replan trigger:** registry gap for this method; second provider pivot;
  retry temptation after null/transport fail.

## Decision capsule

- `DECISION_DELTA`: GTA Create 195 has no `Log truncated` marker; public
  `getTransaction` is the next independent copy of that exact signature.
- `UNCERTAINTY_REMOVED`: whether standard-RPC getTransaction recovers a
  longer Create body than GTA 195.
- `CAPABILITY_OR_EVIDENCE`: one request plus consume/fail on the Create
  candidate.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: if same 195, Create body is the emitted event not a GTA-log cut;
  if longer, retry offline mask on the new length; if null, GTA copy remains
  best available.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: Helius getTransaction (credentialed;
  not in the bound registry as a separate route).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_SOLANA_STANDARD_GET_TRANSACTION_001_AND_A18_REQUEST_SHAPE`

Pinned Create signature from TASK-40 A4 (page hashes unchanged):

`4fi62bv2A67i6rFh6naBrLyVoteXT4EnXaQzK7K2rboujxRy2AxEu5epesgG7hRcT3xhpZx15EKGG4BxxspX61EH`

Route: `SOLANA-STANDARD-GET-TRANSACTION-001` via
`configs/provider_route_capability_registry_v3.yaml`. Endpoint
`https://api.mainnet-beta.solana.com/`. Keyless. `max_requests=1`.
`retry=false`. `fallback=false`. DNS/TCP preflight before the POST.

## Definition of Done

1. Request is standard `getTransaction` json, commitment `confirmed`,
   `maxSupportedTransactionVersion=0`, exact pinned signature. No Helius
   URL, no api-key query, no `.env` read.
2. Classifier terminals are exactly:
   `CREATE_GETTX_SAME_195_STILL_TRUNCATED`,
   `CREATE_GETTX_SAME_195_CONSUMED`,
   `CREATE_GETTX_LONGER_BODY_CONSUMED`,
   `CREATE_GETTX_LONGER_BODY_STILL_TRUNCATED`,
   `CREATE_GETTX_SHORTER_THAN_GTA`,
   `CREATE_GETTX_CREATE_BODY_ABSENT`,
   `CREATE_GETTX_NULL_OR_UNAVAILABLE`,
   `PROVIDER_TYPED_FAILURE`,
   `TRANSPORT_OR_COVERAGE_UNKNOWN`.
3. Same 195 still failing the Create-only two-field candidate is not an
   exclusive XB/RPC-cut claim. A consume of a longer body is not exclusive-cut
   either.
4. Live one-shot if executed writes raw bytes only under local A4. Git
   receipts store hashes/counts only. Missing live raw is an explicit gap,
   not a skip without proof.
5. Targeted tests pass on fixtures. No `SINGLE_AGENT_REVIEW_FALLBACK`. No
   unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth and external authority.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=HELIUS_GETTRANSACTION_ONLY_IF_PUBLIC_RPC_NULL`.

## Authority and non-claims

Owner OK for this one keyless getTransaction is this atom. It does not grant
Helius, pagination, retry, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 or previous H11 science receipts or
the pinned decoder.
