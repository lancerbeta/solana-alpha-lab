---
task_id: FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 54b34090d1d912380e55e8e724351498ed669fb3
  expected_upstream: origin/main
  expected_upstream_oid: 54b34090d1d912380e55e8e724351498ed669fb3
  expected_branch: cursor/fresh-oos-baseline-vs-friction-veto
  dirty_mode: ALLOW_REPORTED
objective: Freeze one fresh OOS baseline-versus-friction-veto Factory experiment as configuration composition over the existing Free-key capture, then run it only after the exact Jupiter phrase, without a hypothesis-specific core runner, VPS, or alpha claim.
managed_write_set:
  - docs/tasks/FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1.md
  - catalog/schemas/factory_v1_friction_veto.schema.json
  - configs/factory_v1_friction_veto_v1.yaml
  - configs/friction_veto_rule_v1.yaml
  - configs/experiment_specs/fresh_oos_baseline_vs_friction_veto_v1.yaml
  - configs/quote_native_fresh_oos_friction_veto_audition_v1.yaml
  - src/solana_alpha_lab/factory/friction_veto.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/cockpit.py
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - tests/test_fresh_oos_baseline_vs_friction_veto.py
  - tests/test_factory_v1_commissioning.py
  - tests/test_factory_v1_owner_cockpit.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_runtime_receipt_v1.json
  - docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_acceptance_v1.json
  - docs/evidence/fresh_oos_friction_veto/a5_delivery_completion_evidence_v1.json
  - docs/evidence/fresh_oos_friction_veto/a5_delivery_independent_review_v1.json
  - docs/evidence/fresh_oos_friction_veto/a5_delivery_factory_fit_v1.json
  - docs/reports/fresh_oos_friction_veto/a5_owner_readout_v1.md
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
  - HYPOTHESIS_SPECIFIC_CORE_RUNNER_CHANGE
  - VPS_PROVIDER_PURCHASE_OR_SSH_OR_DEPLOY_CREDENTIALS
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - MOVE_3_OR_ALPHA_OR_NETRETURN
  - A1_MOVE2_OR_COMMISSIONING_MINT_REUSE
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
    - EVIDENCE-FACTORY-V1-COMMISSIONING-ACCEPTANCE-001
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
      - docs/evidence/fresh_oos_friction_veto/a5_delivery_completion_evidence_v1.json
    HISTORICAL_CONTEXT: []
---

# FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_REORDER`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=REORDER`

ATOM 4 Cockpit-lite is on `main`. A3+A4 were useful operator proofs and
the second consecutive preparatory-only merge. The owner plan to continue
productization (VPS) is rejected now: it would not answer whether the
replicated friction sign is a useful decision.

Owner trigger: take the executive REORDER into work plus `го`. That is not
the Jupiter Free-key phrase, not VPS purchase, and not
`FACTORY_V1_OPERATIONAL_READY`.

Detail misses in the source memo are corrected here: live harness route is
`DIRECT_CURSOR_DELIVERY`, not `DESIGN_ONLY`. Freeze and campaign stay one
atom; the campaign still requires its own exact phrase.

`strongest_rejected_alternative`: real VPS host.
`why_rejected_now`: cash/deploy gate; no new market decision.

## PRD-lite

- **Outcome that must become true:** a frozen monotonic veto
  `VETO_IF_X_LT_SAMPLE_MEDIAN` is applied to a fresh 6+6 outcome-blind
  cohort excluding A1, MOVE 2 and commissioning mints; the owner gets
  `EXTEND_TO_SHADOW` or `CLOSE_EXACT_FRICTION_VETO_FAMILY`.
- **Why now:** three live sign replications exist; a fourth replication
  has low information; Cockpit-lite just closed a preparatory loop.
- **Downstream consumer:** the owner deciding whether this friction family
  may proceed to paper/shadow. VPS remains a later named consumer only if
  unattended collection becomes the bottleneck.
- **Current gap:** capture WRAP is still hardcoded to the commissioning
  phrase/exclusions; no frozen veto projector exists.
- **Success observable:** composition tests with zero network; after the
  exact phrase, one fresh capture plus veto readout.
- **Invalidation:** experiment needs a new core runner; post-hoc threshold
  search; mint reuse; HEALTHY/operational-ready/alpha claims.
- **Non-goals:** alpha/NetReturn, H3600 search, RC-001, new provider, VPS,
  `/execute`, wallet, MOVE 3, production registry seed.

Frozen hypothesis:

- ID: `HYP-FRESH-OOS-BASELINE-VS-FRICTION-VETO-V1`
- Experiment: `EXP-FRESH-OOS-BASELINE-VS-FRICTION-VETO-001`
- Capability: `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`
- Estimand: baseline vs baseline+veto on H900 quoted recovery, not PnL.

## SSD-lite

- **Baseline truth:** `origin/main`
  `54b34090d1d912380e55e8e724351498ed669fb3`. ATOM 1–4 on main. Kernel
  `provider_calls: false`.
- **Design:** ADOPT existing Free-key capture. WRAP `run_campaign` +
  `classify_audition_terminal`. FORK only the `(atom_id, owner_phrase)`
  pair and exclusion set. BUILD the veto projector as configuration over
  receipt cells. Do not change `factory/runner.py`.
- **Composition check:** YES after making capture spec-driven
  (phrase/atom_id/all Git receipt exclusions). That is a reusable
  capability gap from ATOM 2, not a hypothesis-specific core pipeline.
- **Invariants:** Git remains scientific truth; rule frozen before fresh
  Y; UNKNOWN X/Y excluded from scored arms; cash $0; no `.env`.
- **Validation:** fail-closed tests, 0 provider calls without the phrase;
  commissioning isolated tests still pass.
- **Rollback:** revert the branch.

## Decision capsule

- `DECISION_DELTA`: REORDER away from VPS; freeze baseline-vs-veto as the
  next decision-bearing market atom.
- `UNCERTAINTY_REMOVED`: whether using t0 friction as a veto improves the
  H900 quoted-exit distribution on a fresh cohort.
- `CAPABILITY_OR_EVIDENCE`: frozen rule, ExperimentSpec, capture policy,
  spec-driven capture WRAP, veto projector.
- `STOP`: before any Jupiter/credential read until the exact phrase below.
  After capture, at exact-head CI for the merge phrase.
- `NEXT`: if PASS, paper/shadow only under a later exact contract; if
  FAIL, close this veto family without threshold rescue. Not MOVE 3.
- `ADOPTION_ROUTE=WRAP_EXISTING_FREE_KEY_CAPTURE_PLUS_VETO_PROJECTOR`
- `REPLAN_TRIGGER`: core runner must learn veto logic; cheapest falsifier
  cannot run; second consecutive freeze-only merge; VPS/UI pivot.

## Exact live-capture owner phrase

`го` does not satisfy this. Paste the whole line:

`OK FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1: one Jupiter Free-key fresh OOS baseline-vs-friction-veto campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding A1, MOVE 2 and commissioning mints; frozen monotonic veto VETO_IF_X_LT_SAMPLE_MEDIAN; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; WRAP existing capture plus classify_audition_terminal; not MOVE 3; not alpha; not VPS; no post-hoc threshold search.`

## Definition of Done

1. Frozen ExperimentSpec, capture policy, and median-X veto rule exist.
2. Factory capture reads phrase/atom_id/exclusions from spec/policy, not
   a hardcoded commissioning pair.
3. Missing/mismatched phrase returns `BLOCKED_AUTHORITY` with 0 calls.
4. Frozen YAML rule binds the projector; Factory readout applies it to a
   synthetic receipt without network and emits `EXTEND_TO_SHADOW` or
   `CLOSE_EXACT_FRICTION_VETO_FAMILY`.
5. After the exact phrase: one fresh capture, hash-bound receipts, veto
   decision, Catalog, owner readout. No registry seed. No alpha.

## Merge evidence

After live capture, `l2_roles` includes `DELIVERY_EVIDENCE` bound to exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/fresh_oos_friction_veto/a5_delivery_completion_evidence_v1.json`
