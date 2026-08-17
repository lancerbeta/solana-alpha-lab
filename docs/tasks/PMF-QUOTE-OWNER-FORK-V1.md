---
task_id: PMF-QUOTE-OWNER-FORK-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e8a624783553c638992013797a5afc0ad111e5c7
  expected_upstream: origin/main
  expected_upstream_oid: e8a624783553c638992013797a5afc0ad111e5c7
  expected_branch: cursor/pmf-quote-owner-fork
  dirty_mode: ALLOW_REPORTED
objective: Consume the merged PMF quote-cost overlay receipt only and name the missing facts that keep Touch, Fillable and fees fail-closed, without a provider call, execute, taker or signer.
managed_write_set:
  - docs/tasks/PMF-QUOTE-OWNER-FORK-V1.md
  - configs/pmf_quote_owner_fork_v1.yaml
  - src/solana_alpha_lab/pmf_quote_owner_fork.py
  - tests/test_pmf_quote_owner_fork.py
  - scripts/run_pmf_quote_owner_fork.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_owner_fork_runtime_receipt_v1.json
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_owner_fork_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_owner_fork_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_factory_fit_v1.json
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
  - EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-COST-OVERLAY-ACCEPTANCE-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/pmf_quote_owner_fork_v1.yaml
      - configs/pmf_quote_cost_overlay_v1.yaml
      - docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_runtime_receipt_v1.json
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_completion_evidence_v1.json
      - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_independent_review_v1.json
      - docs/evidence/pmf_quote_slice/a1_owner_fork_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-OWNER-FORK-V1

Owner phrase `OK PMF-QUOTE-OWNER-FORK: overlay receipt only, name missing Touch/Fillable/fee facts, no execute`.

WRAP the A26 unpaid-fork pattern and TASK-26 layer vocabulary over the merged overlay receipt. Do not call a provider. Do not execute. Do not promote quote to Touch, Fillable or zero fees.

## Task Outcome Brief

- **Owner decision:** name the exact missing facts that keep Touch, Fillable and fees fail-closed after the overlay, without choosing execute.
- **Product outcome:** one unpaid owner-fork packet — overlay stays bound, missing facts are named, execute remains forbidden.
- **Named consumers:** goal owner choosing stay-overlay versus a later non-execute Touch or fee observation.
- **Cheapest falsifier:** overlay hash drifts; packet promotes a layer; packet offers execute as an authorized next phrase; a provider GET runs.
- **Terminal outcome:** `QUOTE_OWNER_FORK_MISSING_FACTS_NAMED` or `QUOTE_OWNER_FORK_PREREQUISITES_DRIFT`. Not alpha, PIT, cashflow or canonical DONE.
- **User-visible result:** Russian readout naming each missing fact and the unpaid next phrases. Execute is ineligible in this packet.
- **Non-goals:** no provider/network, no credential, no execute/build/taker/signer, no H11 unpark, no H13/H02, no registry rewrite, no canonical DONE.
- **Evidence budget:** git receipts only; zero provider requests; no local full gate before PR.
- **Replan trigger:** overlay receipt hash drifts; TASK-26 layer contract is rewritten; owner authorizes execute instead.

## Decision capsule

- `DECISION_DELTA`: live PMF object becomes an honest unpaid fork over named missing facts, not a fillable price and not execute.
- `UNCERTAINTY_REMOVED`: which exact facts are still missing for Touch, Fillable and fees after the overlay.
- `CAPABILITY_OR_EVIDENCE`: one hash-bound packet from the overlay receipt onto TASK-26 questions.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: do not auto-start execute, H13, H02 or H11. After merge the owner still owes one unpaid fork phrase or may stay silent.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: call Jupiter again, treat `outAmount` as Touch/Fillable, or offer an execute phrase as if authorized.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=WRAP_A26_FORK_PATTERN_OVER_OVERLAY_RECEIPT_AND_TASK26`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-OWNER-FORK: overlay receipt only, name missing Touch/Fillable/fee facts, no execute`

## Unpaid owner phrases (not executed by this atom)

- `OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced`
- `OK PMF-QUOTE-TOUCH-FACT: authorize a non-execute Touch observation`
- `OK PMF-QUOTE-FEE-FACT: authorize a quote-layer fee-field observation, no execute`

Execute / taker / signer remain `INELIGIBLE` in this packet. No execute phrase is offered.

## Definition of Done

1. Packet reads only the frozen overlay runtime receipt and acceptance plus TASK-26 vocabulary; no network, credential, `/execute` or `/build`.
2. Overlay terminal stays `QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED`; identity matches A24 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` / notional `10000000`.
3. Touch, Fillable and fees each name a missing fact; none is promoted; missing fees are not zero.
4. Russian readout names each missing fact, the unpaid phrases, and that execute is ineligible.
5. v6/v7 registries, RC001 freeze, H11 park and the trial ledger are not in the write set.
