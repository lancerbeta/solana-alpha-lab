---
task_id: PMF-QUOTE-COST-OVERLAY-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: feee8007462afb83c12e32a41c886c3d82cbd898
  expected_upstream: origin/main
  expected_upstream_oid: feee8007462afb83c12e32a41c886c3d82cbd898
  expected_branch: cursor/pmf-quote-cost-overlay
  dirty_mode: ALLOW_REPORTED
objective: Consume the merged PMF quote one-shot receipt only and project TASK-26 layers so QUOTE stays observed while Touch, Fillable, fees and NetReturn stay fail-closed not evidenced, with no provider call, execute, taker or signer.
managed_write_set:
  - docs/tasks/PMF-QUOTE-COST-OVERLAY-V1.md
  - configs/pmf_quote_cost_overlay_v1.yaml
  - src/solana_alpha_lab/pmf_quote_cost_overlay.py
  - tests/test_pmf_quote_cost_overlay.py
  - scripts/run_pmf_quote_cost_overlay.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_runtime_receipt_v1.json
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_cost_overlay_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_cost_overlay_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_cost_overlay_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_cost_overlay_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - PROVIDER_OR_NETWORK_CALL
  - CREDENTIAL_OR_API_KEY_READ
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE
  - MISSING_FEE_TREATED_AS_ZERO
  - NETRETURN_OR_CASHFLOW_CLAIM
  - LOCAL_RAW_USED_AS_GIT_TRUTH
  - H11_UNPARK_OR_SAMPLE_CAMPAIGN
  - H13_OR_H02_TRIAL_STARTED
  - RC001_FREEZE_MUTATED
  - V6_OR_V7_REGISTRY_REWRITE
  - TRIAL_LEDGER_REWRITE
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-SLICE-ONE-SHOT-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/pmf_quote_cost_overlay_v1.yaml
      - configs/pmf_quote_slice_one_shot_v1.yaml
      - docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-COST-OVERLAY-V1

Owner phrase `OK PMF-QUOTE-COST-OVERLAY: consume one-shot receipt only, no execute`.

WRAP the frozen TASK-26 layer vocabulary over the already-observed Jupiter V2 quote. Do not call a provider. Do not read a credential. Do not execute. Do not treat a quote as Touch, Fillable, RealizedVWAP or NetReturn. Missing fee fields are not zero.

## Task Outcome Brief

- **Owner decision:** authorize the overlay because a visible quote does not yet say whether the market is touchable, fillable, or money after costs.
- **Product outcome:** one terminal that the overlay is bound — QUOTE observed, Touch/Fillable/fees/NetReturn fail-closed not evidenced.
- **Named consumers:** goal owner; later execute or fill work that must not invent cost from a quote.
- **Cheapest falsifier:** overlay marks Touch or Fillable true; missing fees booked as zero; NetReturn claimed; a new provider GET; `/execute`; local raw bytes used as git truth.
- **Terminal outcome:** `QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED` or `QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT`. Not alpha, PIT, cashflow or canonical DONE.
- **User-visible result:** Russian readout naming the observed quote fields, each layer state, and that execute remains forbidden.
- **Non-goals:** no provider/network, no credential, no execute/build/taker/signer, no H11 unpark, no H13/H02, no registry rewrite, no canonical DONE.
- **Evidence budget:** git receipts only; zero provider requests; no local full gate before PR.
- **Replan trigger:** one-shot receipt hash drifts; TASK-26 layer contract is rewritten; owner authorizes execute instead.

## Decision capsule

- `DECISION_DELTA`: live PMF object becomes an honest quote-cost overlay, not a fillable price and not execute.
- `UNCERTAINTY_REMOVED`: whether the observed `/order` receipt can support Touch, Fillable or computable cost without a new market fact.
- `CAPABILITY_OR_EVIDENCE`: one hash-bound projection from the one-shot receipt onto TASK-26 layers.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: do not auto-start execute, H13, H02 or H11.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: call Jupiter again, wrap TASK-10 Metis, or treat `outAmount` as fill/NetReturn.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=WRAP_TASK26_LAYER_VOCABULARY_OVER_ONE_SHOT_RECEIPT`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-COST-OVERLAY: consume one-shot receipt only, no execute`

## Definition of Done

1. Overlay reads only the frozen one-shot runtime receipt and acceptance; no network, credential, `/execute` or `/build`.
2. QUOTE is `OBSERVED` iff the receipt terminal is `QUOTE_OBSERVED` and identity matches A24 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` / notional `10000000`.
3. Touch, Fillable and RealizedVWAP are `NOT_EVIDENCED`. Fees and NetReturn are `NOT_COMPUTABLE`. Missing fees are not zero.
4. Russian readout names each layer and that this is not DONE/alpha/cashflow/execute.
5. v6/v7 registries, RC001 freeze, H11 park and the trial ledger are not in the write set.
