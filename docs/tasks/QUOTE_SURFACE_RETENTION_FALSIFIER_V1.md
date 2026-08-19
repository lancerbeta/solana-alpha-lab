---
task_id: QUOTE_SURFACE_RETENTION_FALSIFIER_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f64cf39c485fa68715ebb62b50ae5c1ca10cce41
  expected_upstream: origin/main
  expected_upstream_oid: f64cf39c485fa68715ebb62b50ae5c1ca10cce41
  expected_branch: cursor/quote-surface-retention-falsifier
  dirty_mode: ALLOW_REPORTED
objective: Freeze one new quote-surface retention falsifier as configuration composition over the existing Free-key capture, then run it only after the exact Jupiter phrase, without reopening closed t0-friction families, mutating parked RC001 H07/H01, VPS, or an alpha claim.
managed_write_set:
  - docs/tasks/QUOTE_SURFACE_RETENTION_FALSIFIER_V1.md
  - catalog/schemas/experiment_spec.schema.json
  - catalog/schemas/factory_v1_quote_surface_retention_falsifier.schema.json
  - configs/factory_v1_quote_surface_retention_falsifier_v1.yaml
  - configs/quote_surface_retention_rule_v1.yaml
  - configs/experiment_specs/quote_surface_retention_falsifier_v1.yaml
  - configs/quote_native_quote_surface_retention_audition_v1.yaml
  - src/solana_alpha_lab/factory/quote_surface_retention.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - src/solana_alpha_lab/quote_native_live_variation_campaign.py
  - src/solana_alpha_lab/quote_native_evidence_channel_qualification.py
  - tests/test_quote_surface_retention_falsifier.py
  - tests/test_prior_git_t0_friction_screen.py
  - tests/test_factory_v1_owner_cockpit.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_runtime_receipt_v1.json
  - docs/evidence/quote_surface_retention_falsifier/a1_quote_surface_retention_falsifier_acceptance_v1.json
  - docs/evidence/quote_surface_retention_falsifier/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_surface_retention_falsifier/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_surface_retention_falsifier/a1_delivery_factory_fit_v1.json
  - docs/reports/quote_surface_retention_falsifier/a1_owner_readout_v1.md
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
  - TRADED_ONLY_RESCUE
  - CLOSED_T0_FRICTION_FAMILY_REOPENED
  - RC001_H07_H01_UNPARK_OR_MUTATION
  - HYPOTHESIS_SPECIFIC_CORE_RUNNER_CHANGE
  - SECOND_PREPARATORY_ONLY_ATOM
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - ATOM_2_OR_ALPHA_OR_NETRETURN
  - A1_MOVE2_COMMISSIONING_ATOM5_OR_ATOM6_MINT_REUSE
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
    - EVIDENCE-PRIOR-GIT-T0-FRICTION-SCREEN-ACCEPTANCE-001
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
      - docs/evidence/quote_surface_retention_falsifier/a1_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_SURFACE_RETENTION_FALSIFIER_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=REBASE`

ATOM 5 closed `CLOSE_EXACT_FRICTION_VETO_FAMILY` (`STRATUM_UNSTABLE`).
ATOM 6 closed `CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY` (`STRATUM_UNSTABLE`)
and the underlying t0→H900 sign failed 23 concordant / 32 discordant.
`registries/research_cycles.yaml` remains empty, so this atom does **not**
invent `RC-004`. Identity is a new derived family, not an unpark of
`RC001-H07-H01`.

Owner trigger: accept the REBASE and execute Atom 1 until the separate
Jupiter gate. `го` is not the Jupiter Free-key phrase, not VPS, and not
`FACTORY_V1_OPERATIONAL_READY`.

`strongest_rejected_alternative`: `ORGANIC_BUYER_PERSISTENCE_V1`.
`why_rejected_now`: correlated vendor-inferred buyer features and
selection confounding; quote-surface change is already measurable on the
proved Free-key `/order` route.

## PRD-lite

- **Outcome that must become true:** on a fresh 6 RECENT + 6 TRADED
  cohort excluding A1, MOVE 2, commissioning, ATOM 5 and ATOM 6 mints,
  apply a frozen within-token retention rule from T0 to H900; the owner
  gets `FRESH_OOS_REPLICATION_EARNED`,
  `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`, or
  `SAMPLE_INVALID_REPLAN_REQUIRED`.
- **Why now:** absolute t0 friction as a cross-sectional predictor is
  closed. The remaining cheap question is whether executable quote-state
  **change** inside one token over 15 minutes has decision utility for a
  position entered only after those 15 minutes.
- **Downstream consumer:** the owner deciding whether this family may
  earn a later identical OOS atom. Atom 2/3/4 are not created here.
- **Current gap:** capture schedule still sells the T0 buy at H900;
  no frozen KEEP-if-surface-did-not-worsen projector exists.
- **Success observable:** composition tests with zero network; after the
  exact phrase, one fresh capture plus stratum-separated retention
  readout.
- **Invalidation:** experiment needs a new core runner; second
  preparatory-only atom; threshold search; TRADED-only salvage;
  HEALTHY/operational-ready/alpha claims.
- **Non-goals:** reopen t0-friction; unpark RC001 H07/H01; organic/buyer
  search; H02/H13; H240; ML; new provider; paid tier; VPS; `/execute`;
  real money; Atom 2/3/4; `FACTORY_V1_OPERATIONAL_READY`; NetReturn.

Frozen hypothesis:

- ID: `HYP-QUOTE-SURFACE-RETENTION-CONTINUATION-V1`
- Experiment: `EXP-QUOTE-SURFACE-RETENTION-FALSIFIER-001`
- Local cycle token: `RC-QUOTE-SURFACE-RETENTION-001`
  (experiment parameter only; not a `RESEARCH-CYCLE-RC00N` registry row)
- Capability: `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`
- Estimand: KEEP vs baseline on H900→H3600 ForwardQuotedReturn, not PnL.

Frozen rule, zero is physical not fitted:

- `RTF(t) = reverse_out(t) / buy_input(t) - 1`
- `RETENTION_DELTA = RTF(H900) - RTF(T0)`
- KEEP: H900 buy and reverse routes exist AND `RETENTION_DELTA >= 0`
- VETO: `RETENTION_DELTA < 0` OR H900 buy/reverse no-route
- UNKNOWN: transport/schema/data uncertainty; not VETO; not numeric zero
- Outcome Y: `SELL_H3600(outAmount of BUY_H900) / BUY_H900 input - 1`
- H3600 no-route: PathRisk, never numeric zero

Primary analysis: RECENT and TRADED separately. No pooled PASS.
No winner-stratum rescue. Operational validity floor: `>=4`
time-separated complete decision/outcome cells per stratum.

## SSD-lite

- **Baseline truth:** `origin/main`
  `f64cf39c485fa68715ebb62b50ae5c1ca10cce41`. ATOM 5 and ATOM 6 on main.
  Kernel `provider_calls: false`.
- **Design:** ADOPT current Jupiter V2 `/order` route. WRAP existing
  Free-key capture/scheduler so a frozen observation schedule can bind
  H900 buy output into H3600 exact sell. FORK only
  `(atom_id, owner_phrase, exclusions, observation_schedule, call_cap=62)`.
  BUILD one hypothesis-specific pure projector. Do not change
  `factory/runner.py`. Do not mutate closed veto/t0-screen YAML rules.
- **Composition check:** YES. Schedule interpreter honors an explicit
  horizon amount when `parent_id` is absent (new H900 buy). Existing
  T0→SELL_H900 parents keep old behavior.
- **Invariants:** Git remains scientific truth; UNKNOWN != 0 != VETO;
  RECENT/TRADED not pooled for primary verdict; cash $0; no `.env`;
  consumed observations never rewritten.
- **Validation:** fail-closed tests, 0 provider calls without the phrase;
  commissioning, closed-veto and closed-t0-screen isolated tests still
  pass; generic runner file still contains no retention logic.
- **Rollback:** revert the branch. Consumed market bytes stay immutable.

## Decision capsule

- `DECISION_DELTA`: REBASE away from t0-friction threshold rescue to a
  new within-token quote-surface retention family.
- `UNCERTAINTY_REMOVED`: whether T0→H900 executable-surface change has
  decision utility for a hypothetical H900 entry liquidated at H3600.
- `CAPABILITY_OR_EVIDENCE`: frozen rule, ExperimentSpec, capture policy,
  schedule WRAP, retention projector.
- `STOP`: before any Jupiter/credential read until the exact phrase
  below. After capture, at exact-head CI for the merge phrase.
- `NEXT`: if PASS, Atom 2 only under a later exact contract; if FAIL,
  close this family; if INCONCLUSIVE, REPLAN, no automatic recapture.
- `ADOPTION_ROUTE=WRAP_EXISTING_FREE_KEY_CAPTURE_PLUS_RETENTION_PROJECTOR`
- `REPLAN_TRIGGER`: core runner must learn retention logic; cheapest
  falsifier cannot run; second preparatory-only atom; provider/route
  pivot; threshold search; single-stratum salvage.

## Exact live-capture owner phrase

`го` does not satisfy this. Paste the whole line:

```
OK QUOTE_SURFACE_RETENTION_FALSIFIER_V1: one Jupiter Free-key quote-surface retention falsifier; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 62; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding A1, MOVE 2, commissioning, ATOM 5 veto and ATOM 6 t0-screen mints; frozen KEEP if RETENTION_DELTA >= 0 and H900 routes exist; H3600 exact sell of BUY_H900 outAmount; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; WRAP existing capture plus retention projector; not Atom 2; not alpha; not VPS; no post-hoc threshold search; no TRADED-only rescue.
```

## Definition of Done

1. Frozen ExperimentSpec, capture policy, and retention rule exist.
2. Observation schedule is T0 buy/reverse, H900 buy/reverse, H3600 sell
   of BUY_H900; SELL_H900 of the T0 buy is not the searchable Y.
3. Missing/mismatched phrase returns `BLOCKED_AUTHORITY` with 0 calls.
4. Frozen YAML rule binds the projector; Factory readout applies it to a
   synthetic receipt without network and emits one of the three
   terminals. RECENT and TRADED are not pooled for PASS.
5. `factory/runner.py` still contains no hypothesis business logic.
6. After the exact phrase: one fresh capture, hash-bound receipts,
   Catalog, owner readout. No registry seed. No alpha.

## Merge evidence

After live capture, `l2_roles` includes `DELIVERY_EVIDENCE` bound to exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/quote_surface_retention_falsifier/a1_delivery_completion_evidence_v1.json`
