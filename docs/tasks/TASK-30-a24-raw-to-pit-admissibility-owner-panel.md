---
task_id: TASK-30
task_version: '24.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ef6da7f95ed797f1106b1a176eb139006727a9c3
  expected_upstream: origin/main
  expected_upstream_oid: ef6da7f95ed797f1106b1a176eb139006727a9c3
  expected_branch: cursor/task30-a24-raw-to-pit-admissibility
  dirty_mode: ALLOW_REPORTED
objective: Convert the exact A22+A23 retained batch into a typed 96-slot admissibility decision for RC001 without any external read.
managed_write_set:
  - docs/tasks/TASK-30-a24-raw-to-pit-admissibility-owner-panel.md
  - docs/contracts/task30_a24_raw_to_pit_admissibility_owner_panel_contract_v1.md
  - configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml
  - catalog/schemas/task30_a24_raw_to_pit_admissibility_owner_panel.schema.json
  - src/solana_alpha_lab/task30_raw_to_pit_admissibility.py
  - scripts/run_task30_a24_raw_to_pit_admissibility.py
  - tests/fixtures/task30/raw_to_pit_admissibility_v1.json
  - tests/test_task30_a24_raw_to_pit_admissibility.py
  - src/solana_alpha_lab/pumpswap_touch_probe.py
  - tests/test_task09_pumpswap_touch_probe.py
  - docs/evidence/task30/a24_raw_to_pit_admissibility_runtime_receipt_v1.json
  - docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json
  - docs/reports/task30/a24_raw_to_pit_admissibility_owner_readout_v1.md
  - docs/evidence/task30/a24_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a24_delivery_independent_review_v1.json
  - docs/evidence/task30/a24_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - local/task30_a24_raw_to_pit_admissibility/**
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - INPUT_HASH_DRIFT
  - TERMINAL_PAGINATION_DRIFT
  - PROVIDER_OR_CREDENTIAL_CALL_REQUIRED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
  - EVENT_COVERAGE_UNRECONCILED
  - UNKNOWN_MARKET_DISCRIMINATOR
  - PUBLIC_SCHEMA_OR_RC001_MEANING_CHANGE
  - MISSING_TO_ZERO_OR_FLAT_COERCION
  - TASK30_OR_RC001_PROMOTION
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T30-A22-HELIUS-GTA-001
    - EVIDENCE-T30-A23-HELIUS-PAGINATION-001
    - CONTRACT-T30-H07-H01-DATA-CONTRACT-GATE-001
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - MODULE-T09-PUMPSWAP-TOUCH-DECODER-001
    - MODULE-T09-PUMPSWAP-TOUCH-PROBE-001
  l2_roles: [DELIVERY_EVIDENCE, ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/decisions/ADR-002-mvp-stack.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a24_raw_to_pit_admissibility_runtime_receipt_v1.json
      - docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json
      - docs/evidence/task30/a24_delivery_completion_evidence_v1.json
      - docs/evidence/task30/a24_delivery_independent_review_v1.json
      - docs/evidence/task30/a24_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A24 — Raw-to-PIT admissibility owner panel

## Task Outcome Brief

- **Owner decision:** decide whether the exact retained pool/day supports a reproducible, explicitly limited 15-minute diagnostic panel for frozen H07/H01, or name the exact missing data capability.
- **Product outcome:** one terminal owner decision that changes the next product action. A decoder, schema or 96 rows without that decision is not success.
- **Named consumer:** `RC001-H07-H01-LIQUIDITY-RETENTION`.
- **Cheapest falsifier:** reproduce exact input counts, attribute all PumpSwap events, and determine whether the 14 truncated-log transactions can be reconciled without inventing market observations.
- **Terminal outcomes:** `LIMITED_DIAGNOSTIC_PANEL_READY`, `TARGETED_PROVIDER_CAPABILITY_GAP_PROVEN`, `REDESIGN_DATA`, or `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** machine-readable decision JSON, a concise Russian owner readout, and a 96-slot coverage summary.
- **Evidence budget:** two retained raw inputs, zero external reads, about 20 minutes for the cheapest falsifier and 120 minutes for the full atom.
- **Non-goals:** TASK-30 acceptance or DONE; H07/H01 trial execution; alpha or strategy promotion; continuous-price claim by forward-fill; missing-to-zero or missing-to-flat coercion; route persistence, fillability, settlement, PnL or NetReturn; provider purchase, retry, fallback or second provider; Parquet/DuckDB production integration; UI, deploy, scheduler or background collection.
- **Replan trigger:** input hash drift; a provider call or credential becomes necessary; a second provider or route is proposed; event coverage cannot be reconciled from retained bytes; public schema or RC001 meaning must change; full atom exceeds evidence or time budget; output only prepares another decoder without changing the owner decision.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=WRAP_EXISTING_DECODER_AND_DATA_CONTRACTS`

`OWNER_CAPTURE_PHRASE=OK T30-A24 RAW_TO_PIT_ADMISSIBILITY_OWNER_PANEL`

## Frozen mission fields

- **DECISION_DELTA:** whether the paid-with-zero A22+A23 batch already yields a typed 96-slot diagnostic, or which exact capability is still missing.
- **UNCERTAINTY_REMOVED:** raw acquisition vs honest panel/PIT admissibility for the named H07/H01 consumer.
- **CAPABILITY_OR_EVIDENCE:** transaction-envelope attribution, instruction/event reconciliation, 96-slot projection and one terminal owner decision. No new provider abstraction.
- **STOP:** zero provider/credential/network calls; no TASK-30 or RC001 promotion; no missing-to-zero/flat; no second provider.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. The terminal decision then tells the owner whether to run one limited diagnostic, start targeted provider research, redesign the estimand, or resolve an integrity conflict.

## Definition of Done

1. Exact A22/A23 raw identities and terminal pagination are reproduced independently and fail on drift.
2. Instruction/event reconciliation is complete or returns a typed terminal gap. Log truncation is an explicit coverage condition.
3. All target trades and exclusions are deterministic and idempotent. Discriminator `929fbdac925838f4` is classified as non-market only through the pinned official IDL/Anchor event binding.
4. Exactly 96 slot records exist with no implicit zero, flat or forward-fill.
5. PIT timestamps and retrospective/prospective limitations are explicit. Historical retrieval is not backdated to `blockTime`.
6. One terminal owner decision is produced.
7. Existing decoder and direct consumers remain green.
8. Code, goal/DoD and architecture review pass.
9. Harness, focused tests, Catalog/generated, secret and diff checks pass.
10. Exact-head CI passes; merge follows repository owner-attention policy. Merge is not semantic acceptance.

## Authority and non-claims

The owner authorized this exact offline atom after the DESIGN_ONLY proposal. Provider, credential, purchase, deployment, wallet, signer, transaction, repository-setting and destructive actions remain forbidden. `TASK-30` remains `BLOCKED_DATA`. RC001 definition bytes stay frozen.
