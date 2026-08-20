---
task_id: PMF-QUOTE-STAY-OVERLAY-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5975685ec093ad0247954be7e56e58e1a0e2799f
  expected_upstream: origin/main
  expected_upstream_oid: 5975685ec093ad0247954be7e56e58e1a0e2799f
  expected_branch: cursor/pmf-quote-stay-overlay
  dirty_mode: ALLOW_REPORTED
objective: Consume the merged owner-fork packet and confirmatory family-close receipts only, bind the unpaid stay-overlay phrase, and freeze quote-only KEEP screening as exhausted without a provider call, fillable-named KEEP, or Touch/Fee capture.
managed_write_set:
  - docs/tasks/PMF-QUOTE-STAY-OVERLAY-V1.md
  - configs/pmf_quote_stay_overlay_v1.yaml
  - src/solana_alpha_lab/pmf_quote_stay_overlay.py
  - tests/test_pmf_quote_stay_overlay.py
  - scripts/run_pmf_quote_stay_overlay.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_runtime_receipt_v1.json
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_stay_overlay_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_factory_fit_v1.json
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
  - FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY
  - QUOTE_ONLY_KEEP_SCREENING_REOPENED
  - QUOTED_PATH_QUALITY_6_PLUS_6_WITHOUT_NEW_PHRASE
  - TOUCH_FACT_AUTO_STARTED
  - FEE_FACT_AUTO_STARTED
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
  - ATOM_2_FROM_RETENTION
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-OWNER-FORK-ACCEPTANCE-001
    - EVIDENCE-QUOTE-SURFACE-RETENTION-CONFIRMATORY-ACCEPTANCE-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/pmf_quote_stay_overlay_v1.yaml
      - configs/pmf_quote_owner_fork_v1.yaml
      - docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_owner_fork_acceptance_v1.json
      - docs/evidence/quote_surface_retention_confirmatory/c1_quote_surface_retention_confirmatory_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_completion_evidence_v1.json
      - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_independent_review_v1.json
      - docs/evidence/pmf_quote_slice/a1_stay_overlay_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-STAY-OVERLAY-V1

Owner phrase `OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced`.

WRAP the unpaid stay-overlay fork over the merged owner-fork packet plus the confirmatory family-close receipts. Do not call a provider. Do not start Touch-fact, Fee-fact, attempt, or another quote-only 6+6.

## Task Outcome Brief

- **Owner decision:** accept that quote cannot evidence Touch, Fillable or fees, and freeze quote-only KEEP screening as exhausted after confirmatory FAIL versus eligible baseline.
- **Product outcome:** one hash-bound stay-overlay packet: overlay missing facts remain fail-closed, retention family stays closed, fillable-named KEEP on `/order` is forbidden, Touch/Fee phrases remain unpaid. Overlay identity remains A24 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` / notional `10000000`.
- **Named consumers:** goal owner choosing a later non-execute Touch observation, a Factory-cockpit without KEEP, or silence; not a Jupiter capture agent.
- **Cheapest falsifier:** owner-fork or confirmatory hashes drift; packet promotes a layer; packet starts Touch/Fee/6+6; a provider GET runs.
- **Terminal outcome:** `QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED` or `QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT`. Not alpha, PIT, cashflow, operational-ready or canonical DONE.
- **User-visible result:** Russian readout that quote-only KEEP screening is exhausted, Fillable is still not evidenced, and Jupiter is not started.
- **Non-goals:** no provider/network, no credential, no execute/build/taker/signer, no fillable KEEP 6+6, no quoted-path 6+6, no Touch/Fee capture, no Factory cockpit, no H11 unpark, no Atom 2, no VPS, no canonical DONE.
- **Evidence budget:** git receipts only; zero provider requests; no local full gate before PR.
- **Replan trigger:** confirmatory scientific terminal is rewritten; owner-fork missing facts are promoted; owner authorizes Touch-fact, Fee-fact, attempt or a new quote-only KEEP instead.

## Decision capsule

- `DECISION_DELTA`: quote-native KEEP path to PMF is closed in Git; next live work cannot pretend Fillable exists on `/order`.
- `UNCERTAINTY_REMOVED`: whether another quote-only 6+6 (fillable/path-risk or hop-count) is an honest next atom. It is not.
- `CAPABILITY_OR_EVIDENCE`: one stay-overlay packet consuming owner-fork + confirmatory close, with a frozen design probe that path-risk KEEP has no contrast and hop_count==1 is underpowered on C1.
- `STOP`: after green exact-head CI; do not merge until the owner phrase bound to this PR/head.
- `NEXT`: do not auto-start Touch-fact, Fee-fact, attempt, Atom 2 or Jupiter. After merge the owner may later authorize Touch-fact or a Factory-cockpit without KEEP.
- `SPEC_ROUTE=BOTH`
- `ROADMAP_VERDICT=REBASE`
- `strongest_rejected_alternative`: fillable/path-risk KEEP 6+6, quoted-path hop_count KEEP 6+6, Atom 2 / TRADED-only / post-hoc thresholds / VPS.
- `why_rejected_now`: confirmatory already tested hours and KEEP; fillable cannot be observed on quote; C1 path-risk never fired; hop_count==1 has no RECENT contrast and TRADED n=3 below floor.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=WRAP_OWNER_FORK_AND_CONFIRMATORY_CLOSE_NO_PROVIDER`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced`

## PRD-lite

- **Outcome:** stay-overlay bound; quote-only KEEP screening exhausted; Touch/Fillable/fees not evidenced from quote.
- **Consumer:** owner deciding the next data class, not another `/order` KEEP.
- **Gap:** unpaid stay-overlay phrase was named but not executed; confirmatory closed retention KEEP; a fillable-named 6+6 would violate TASK-26.
- **Success:** binder PASS, 0 provider, remaining unpaid phrases are Touch-fact and Fee-fact only, fillable KEEP forbidden.
- **Invalidation:** promoting quote to Fillable; reopening quote-only KEEP without a new phrase; treating this packet as operational-ready.
- **Non-goals:** Jupiter, Touch observation, attempt/taker, Factory cockpit implementation, NetReturn.

## SSD-lite

- **Baseline truth:** `origin/main` `5975685ec093ad0247954be7e56e58e1a0e2799f` (PR #158 confirmatory merge).
- **Design:** WRAP owner-fork binder + confirmatory acceptance; FORK atom_id, stay phrase, screening-exhausted terminal, remaining unpaid phrases; BUILD forbidden beyond this packet.
- **Invariants:** UNKNOWN ≠ 0; missing fees ≠ 0; quote ≠ Touch ≠ Fillable; C1/PR156 scientific terminals not rewritten; cash $0; kernel provider_calls not flipped.
- **Affected surfaces:** new stay-overlay module/config/tests/receipts/Catalog append; no factory runner, no v6/v7, no RC001, no trial ledger.
- **Failure modes:** hash drift; execute phrase offered; 6+6 started; catalog hash mismatch.
- **Validation:** targeted stay-overlay tests; isolated code + goal/DoD + architecture critics; exact-head CI.
- **Rollback:** revert this atom's tracked outputs only.

## Remaining unpaid phrases (this atom does not execute them)

- `OK PMF-QUOTE-TOUCH-FACT: authorize a non-execute Touch observation`
- `OK PMF-QUOTE-FEE-FACT: authorize a quote-layer fee-field observation, no execute`

Execute / taker / signer remain `INELIGIBLE`. Attempt-prep stays a frozen offline contract, not started.

## Definition of Done

1. Packet reads only the frozen owner-fork and confirmatory receipts plus TASK-26 vocabulary; no network, credential, `/execute` or `/build`.
2. Owner-fork terminal stays `QUOTE_OWNER_FORK_MISSING_FACTS_NAMED`; overlay Touch/Fillable stay `NOT_EVIDENCED`; fees stay `NOT_COMPUTABLE` and not zero.
3. Confirmatory scientific/product terminal stays `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`; Atom 2 is false; operational-ready is false.
4. Quote-only KEEP screening is `EXHAUSTED`; fillable-named KEEP on quote-only is forbidden; hop_count KEEP 6+6 is not authorized.
5. Russian readout states the close, the remaining unpaid phrases, and that Jupiter is not started.
6. v6/v7 registries, RC001 freeze, H11 park and the trial ledger are not in the write set.
