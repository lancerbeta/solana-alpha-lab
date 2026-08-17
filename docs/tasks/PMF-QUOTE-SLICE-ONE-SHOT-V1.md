---
task_id: PMF-QUOTE-SLICE-ONE-SHOT-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6e47c092d09f2851f3cf3425b363b2d4eb03d42b
  expected_upstream: origin/main
  expected_upstream_oid: 6e47c092d09f2851f3cf3425b363b2d4eb03d42b
  expected_branch: cursor/pmf-quote-slice-one-shot
  dirty_mode: ALLOW_REPORTED
objective: One authorized Jupiter Swap V2 GET /swap/v2/order without taker for SOL to the A24 base mint at 0.01 SOL, quote layer only, portal key allowed, no execute, then persist a sanitized observed receipt and close the live registry gap with v7.
managed_write_set:
  - docs/tasks/PMF-QUOTE-SLICE-ONE-SHOT-V1.md
  - configs/pmf_quote_slice_one_shot_v1.yaml
  - src/solana_alpha_lab/pmf_quote_slice_one_shot.py
  - tests/test_pmf_quote_slice_one_shot.py
  - scripts/run_pmf_quote_slice_one_shot.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_one_shot_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_factory_fit_v1.json
  - configs/provider_route_capability_registry_v7.yaml
  - catalog/schemas/provider_route_capability_registry_v7.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v7.py
  - tests/test_provider_route_capability_registry_v7.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - PERSIST_TRANSACTION_BYTES
  - WRAP_TASK10_METIS_LOGGER
  - FAKE_V7_WITHOUT_OBSERVED_RECEIPT
  - H11_UNPARK_OR_SAMPLE_CAMPAIGN
  - H13_OR_H02_TRIAL_STARTED
  - NOTIONAL_BUCKET_SET_V1_FROZEN
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
  - RC001_FREEZE_MUTATED
  - TRIAL_LEDGER_REWRITE
  - V6_REGISTRY_REWRITE
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-SLICE-ONE-SHOT-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/pmf_quote_slice_v1.yaml
      - configs/pmf_quote_slice_one_shot_v1.yaml
      - configs/provider_route_capability_registry_v6.yaml
      - configs/provider_route_capability_registry_v7.yaml
      - configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_completion_evidence_v1.json
      - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_independent_review_v1.json
      - docs/evidence/pmf_quote_slice/a1_one_shot_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-SLICE-ONE-SHOT-V1

Owner phrase `OK PMF-QUOTE-SLICE-ONE-SHOT: Jupiter Swap V2 /order without taker, SOL to A24 base mint 0.01 SOL, quote layer only, portal key allowed, no execute`.

One GET to official `https://api.jup.ag/swap/v2/order` without `taker`. Header auth is `JUPITER_API_KEY` (`x-api-key`). Quote layer only. No `/execute`, `/build`, signer or transaction persistence. v6 stays immutable. v7 is allowed only after this observed receipt.

## Task Outcome Brief

- **Owner decision:** authorize the bound quote-slice call because a visible price requires one observed `/order` without taker.
- **Product outcome:** one sanitized quote observation and, if HTTP 200 with quote fields and `transaction is null`, a v7 registry row.
- **Named consumers:** goal owner; later cost/NetReturn work that must not wrap Metis or execute.
- **Cheapest falsifier:** request includes `taker`; `/execute` is called; transaction bytes enter git; v7 is written without this receipt; identity drifts from A24 base mint.
- **Terminal outcome:** `QUOTE_OBSERVED` or a typed transport/provider failure. Not alpha, PIT, cashflow or canonical DONE.
- **User-visible result:** Russian readout with outAmount/router if present, whether a call happened, and that execute remains forbidden.
- **Non-goals:** no execute, no wallet, no H11 unpark, no H13/H02, no Metis logger, no v6 rewrite.
- **Evidence budget:** one provider GET, one credential read, git receipt plus local raw outside git.
- **Replan trigger:** official `/order` without taker no longer quotes; portal key missing; identity retired.

## Decision capsule

- `DECISION_DELTA`: live PMF object becomes an observed quote, not a registry gap.
- `UNCERTAINTY_REMOVED`: whether Jupiter V2 `/order` without taker returns a price for this A24 mint at 0.01 SOL.
- `CAPABILITY_OR_EVIDENCE`: one observed GET and v7 only if the receipt exists.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: do not auto-start execute, H13, H02 or H11.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: wrap TASK-10 Metis `/swap/v1/quote`, or skip the live call and fake v7.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-SLICE-ONE-SHOT: Jupiter Swap V2 /order without taker, SOL to A24 base mint 0.01 SOL, quote layer only, portal key allowed, no execute`

## Definition of Done

1. Exactly one GET `/swap/v2/order` without `taker`. Query is inputMint=SOL, outputMint=A24 base mint, amount=10000000.
2. Credential is `JUPITER_API_KEY` in `x-api-key` only, never in the URL. Alias `JUPITER_PORTAL_API_KEY` is allowed if the official name is empty.
3. `/execute` and `/build` are absent. Transaction bytes are not written to git.
4. v6 bytes unchanged. v7 exists only if this atom produced an observed receipt.
5. Russian readout names the observed price fields or the typed failure, and that this is not DONE/alpha/cashflow.
