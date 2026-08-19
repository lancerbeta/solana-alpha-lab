---
task_id: PRIOR_GIT_T0_FRICTION_SCREEN_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fff57a8af6bf2753d27ae91220357fad08c7fa84
  expected_upstream: origin/main
  expected_upstream_oid: fff57a8af6bf2753d27ae91220357fad08c7fa84
  expected_branch: cursor/prior-git-t0-friction-screen
  dirty_mode: ALLOW_REPORTED
objective: Freeze one prior-Git t0 friction-screen Factory experiment as configuration composition over the existing Free-key capture, then run it only after the exact Jupiter phrase, without reopening the closed ATOM 5 median-X family, VPS, or an alpha claim.
managed_write_set:
  - docs/tasks/PRIOR_GIT_T0_FRICTION_SCREEN_V1.md
  - catalog/schemas/factory_v1_prior_git_t0_friction_screen.schema.json
  - configs/factory_v1_prior_git_t0_friction_screen_v1.yaml
  - configs/prior_git_t0_friction_screen_rule_v1.yaml
  - configs/experiment_specs/prior_git_t0_friction_screen_v1.yaml
  - configs/quote_native_prior_git_t0_friction_screen_audition_v1.yaml
  - src/solana_alpha_lab/factory/t0_friction_screen.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - tests/test_prior_git_t0_friction_screen.py
  - tests/test_fresh_oos_baseline_vs_friction_veto.py
  - tests/test_factory_v1_owner_cockpit.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/prior_git_t0_friction_screen/a6_prior_git_t0_friction_screen_runtime_receipt_v1.json
  - docs/evidence/prior_git_t0_friction_screen/a6_prior_git_t0_friction_screen_acceptance_v1.json
  - docs/evidence/prior_git_t0_friction_screen/a6_delivery_completion_evidence_v1.json
  - docs/evidence/prior_git_t0_friction_screen/a6_delivery_independent_review_v1.json
  - docs/evidence/prior_git_t0_friction_screen/a6_delivery_factory_fit_v1.json
  - docs/reports/prior_git_t0_friction_screen/a6_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
  - POST_HOC_THRESHOLD_SEARCH
  - ATOM5_SAMPLE_MEDIAN_REUSED_AS_CUTOFF
  - HYPOTHESIS_SPECIFIC_CORE_RUNNER_CHANGE
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - MOVE_3_OR_ALPHA_OR_NETRETURN
  - A1_MOVE2_COMMISSIONING_OR_ATOM5_MINT_REUSE
  - PRODUCTION_REGISTRY_SEED
  - WALLET_SIGNER_TX_OR_CASH
  - PAID_PLAN_OR_SECOND_PROVIDER
  - EXECUTE_BUILD_OR_TAKER
  - KERNEL_PROVIDER_CALLS_TRUE
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
    - CONFIG-FACTORY-V1-PRODUCT-KERNEL-001
    - EVIDENCE-FRESH-OOS-FRICTION-VETO-ACCEPTANCE-001
    - MODULE-FACTORY-V1-CAPABILITY-FREE-KEY-CAPTURE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# PRIOR_GIT_T0_FRICTION_SCREEN_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_SELECT`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP_REORDER_PATCH_NEXT_CONTENT`

ATOM 5 closed the in-sample median-X veto family
(`CLOSE_EXACT_FRICTION_VETO_FAMILY`, `STRATUM_UNSTABLE`). The owner
decision is that close, not the audition hint. The next cheapest market
question is whether a **pre-frozen t0 cutoff** computed only from already
Git-canonical complete-XY **X** has decision utility on a fresh cohort.

Owner trigger: take this SELECT into work plus `го`. That is not the
Jupiter Free-key phrase, not VPS purchase, and not
`FACTORY_V1_OPERATIONAL_READY`.

`strongest_rejected_alternative`: VPS / paper-shadow on the closed veto
family / new threshold from ATOM 5's peeked sample median / fourth
sign-only replication.
`why_rejected_now`: no EXTEND consumer; peeking; cash/deploy.

## PRD-lite

- **Outcome that must become true:** on a fresh 6 RECENT + 6 TRADED
  cohort excluding A1, MOVE 2, commissioning and ATOM 5 veto-campaign
  mints, apply a frozen t0 cutoff computed only from prior Git
  complete-XY X; the owner gets `EXTEND_TO_SHADOW` or
  `CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY`.
- **Why now:** the closed veto showed an in-sample median is not a
  deployable t0 policy. The cheapest next falsifier is a pre-frozen
  cutoff that cannot see the new campaign's Y.
- **Downstream consumer:** the owner deciding whether this t0-screen
  family may proceed to paper/shadow under a later exact contract.
- **Current gap:** no YAML-bound projector with a numeric cutoff frozen
  and hash-bound before any credential read.
- **Success observable:** composition tests with zero network; after the
  exact phrase, one fresh capture plus t0-screen readout.
- **Invalidation:** experiment needs a new core runner; ATOM 5 sample
  median reused as cutoff; post-hoc threshold search; mint reuse;
  HEALTHY/operational-ready/alpha claims.
- **Non-goals:** ATOM 5 threshold rescue, H3600 as searchable Y,
  NetReturn, VPS, `/execute`, registry seed, MOVE 3,
  `FACTORY_V1_OPERATIONAL_READY`.

Frozen hypothesis:

- ID: `HYP-PRIOR-GIT-T0-FRICTION-SCREEN-V1`
- Experiment: `EXP-PRIOR-GIT-T0-FRICTION-SCREEN-001`
- Capability: `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`
- Estimand: baseline vs baseline+frozen-t0-screen on H900 quoted recovery, not PnL.
- Frozen cutoff: `-0.0205835` = median of 33 complete-XY X from A1 + MOVE 2 + commissioning. Not ATOM 5 `-0.0116887`.

## SSD-lite

- **Baseline truth:** `origin/main`
  `fff57a8af6bf2753d27ae91220357fad08c7fa84`. ATOM 5 on main. Kernel
  `provider_calls: false`.
- **Design:** ADOPT existing Free-key capture. WRAP `run_campaign` +
  `classify_audition_terminal` + veto overlay pattern. FORK only the
  `(atom_id, owner_phrase)` pair and expanded exclusion set. BUILD the
  t0-screen projector as configuration over receipt cells with the
  numeric cutoff frozen before credential read. Do not change
  `factory/runner.py`. Do not mutate `configs/friction_veto_rule_v1.yaml`.
- **Composition check:** YES. Capture remains spec-driven.
- **Invariants:** Git remains scientific truth; cutoff frozen before
  fresh Y; UNKNOWN X/Y excluded from scored arms; cash $0; no `.env`.
- **Validation:** fail-closed tests, 0 provider calls without the phrase;
  commissioning and closed-veto isolated tests still pass.
- **Rollback:** revert the branch.

## Decision capsule

- `DECISION_DELTA`: freeze a prior-Git t0 cutoff screen instead of
  reopening the closed in-sample median-X family or jumping to VPS.
- `UNCERTAINTY_REMOVED`: whether a pre-frozen t0 friction cutoff has
  decision utility on a fresh cohort.
- `CAPABILITY_OR_EVIDENCE`: frozen rule, ExperimentSpec, capture policy,
  t0-screen projector, spec-driven capture WRAP.
- `STOP`: before any Jupiter/credential read until the exact phrase
  below. After capture, at exact-head CI for the merge phrase.
- `NEXT`: if PASS, paper/shadow only under a later exact contract; if
  FAIL, close this t0-screen family without threshold rescue. Not MOVE 3.
- `ADOPTION_ROUTE=WRAP_EXISTING_FREE_KEY_CAPTURE_PLUS_T0_SCREEN_PROJECTOR`
- `REPLAN_TRIGGER`: core runner must learn screen logic; cheapest
  falsifier cannot run; second consecutive freeze-only merge; VPS/UI
  pivot.

## Exact live-capture owner phrase

`го` does not satisfy this. Paste the whole line:

```
OK PRIOR_GIT_T0_FRICTION_SCREEN_V1: one Jupiter Free-key prior-Git t0 friction-screen campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding A1, MOVE 2, commissioning and ATOM 5 veto-campaign mints; frozen t0 cutoff from prior Git complete-XY X only, not the closed ATOM 5 sample median; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; WRAP existing capture plus classify_audition_terminal; not MOVE 3; not alpha; not VPS; no post-hoc threshold search.
```

## Definition of Done

1. Frozen ExperimentSpec, capture policy, and prior-Git t0 cutoff rule exist.
2. YAML cutoff equals median(X | complete XY) from A1 + MOVE 2 +
   commissioning receipts and is not the ATOM 5 sample median.
3. Missing/mismatched phrase returns `BLOCKED_AUTHORITY` with 0 calls.
4. Frozen YAML rule binds the projector; Factory readout applies it to a
   synthetic receipt without network and emits `EXTEND_TO_SHADOW` or
   `CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY`.
5. After the exact phrase: one fresh capture, hash-bound receipts, t0
   decision, Catalog, owner readout. No registry seed. No alpha.

## Merge evidence

After live capture, `l2_roles` includes `DELIVERY_EVIDENCE` bound to exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/prior_git_t0_friction_screen/a6_delivery_completion_evidence_v1.json`
