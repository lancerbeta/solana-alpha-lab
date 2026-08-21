---
task_id: IN_SCOPE_POPULATION_FIT_RECONCILIATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2520bed9a48ab426b1374621866caea3b51441da
  expected_upstream: origin/main
  expected_upstream_oid: 2520bed9a48ab426b1374621866caea3b51441da
  expected_branch: cursor/in-scope-population-fit-reconciliation
  dirty_mode: ALLOW_REPORTED
objective: Zero-provider decision atom that reconciles named Git quote-native H900 receipts into a campaign-level population matrix and either freezes an in-scope EARLY/SEASONED contract for ATOM 2 or stops the branch.
managed_write_set:
  - docs/tasks/IN_SCOPE_POPULATION_FIT_RECONCILIATION_V1.md
  - configs/in_scope_population_fit_reconciliation_v1.yaml
  - src/solana_alpha_lab/in_scope_population_fit_reconciliation.py
  - scripts/run_in_scope_population_fit_reconciliation.py
  - tests/test_in_scope_population_fit_reconciliation.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/in_scope_population_fit_reconciliation/a1_runtime_receipt_v1.json
  - docs/evidence/in_scope_population_fit_reconciliation/a1_acceptance_v1.json
  - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_completion_evidence_v1.json
  - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_independent_review_v1.json
  - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_factory_fit_v1.json
  - docs/reports/in_scope_population_fit_reconciliation/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_OR_NETWORK_CALL
  - CREDENTIAL_OR_API_KEY_READ
  - FACTORY_RUNNER_CHANGE
  - REPROJECT_COUNTED_AS_NEW_MARKET_OBSERVATION
  - TRADED_ACCEPTED_AS_PRODUCT_POPULATION
  - Y_EQUALS_X_TREATED_AS_TIME_SEPARATED
  - UNKNOWN_AS_ZERO
  - H3600_OR_H4_USED_AS_Y
  - FOURTH_X_OR_FEATURE_TOURNAMENT
  - POST_HOC_THRESHOLD_SEARCH
  - SECOND_PREPARATORY_ONLY_ATOM
  - NEW_PROVIDER_OR_PAID_PLAN
  - WALLET_SIGNER_TX_OR_CASH
  - ALPHA_OR_NETRETURN
  - ARCHITECTURE_INTENT_OR_ROADMAP
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - EVIDENCE-FRESH-OOS-FRICTION-VETO-RUNTIME-001
    - EVIDENCE-PRIOR-GIT-T0-FRICTION-SCREEN-RUNTIME-001
    - EVIDENCE-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001
    - MODULE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_completion_evidence_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_independent_review_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_delivery_factory_fit_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_runtime_receipt_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json
      - docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_runtime_receipt_v1.json
      - docs/evidence/ordinary_recent_early_path_h900_audition/a1_ordinary_recent_early_path_h900_audition_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# IN_SCOPE_POPULATION_FIT_RECONCILIATION_V1

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ADOPTION_ROUTE=ADOPT_NAMED_GIT_RECEIPTS_WRAP_THIN_OFFLINE_PROJECTOR_BUILD_NO_FACTORY_RUNNER`

Owner direction: `muv-4.md` / `PMF_POPULATION_TO_STATE_RULE_V1` ATOM 1.
This is the Git contract. The memo is product direction, not a bypass of
harness or provider gates.

## Entry patches against live Git

1. Quote-native `RECENT` is **ultra-fresh** (~16–69s), not product `EARLY`
   (5–15m). Only the early-path campaign is in-scope 5–15m.
2. `#168` MEU reproject is a **classification overlay** on that same capture,
   not a seventh market observation.
3. `y_equals_x` is excluded from time-separated numeric H900.
4. `TRADED` ages span minutes to years and launchpad is not on frozen cells;
   it remains a control source, never the product population. A TRADED row
   whose age falls in 5–15m is source-band traffic, not product EARLY Y.
5. Seasoned bounds stay `30m–120m` because historical TRADED *source* traffic
   is not empty in that band. Bounds may change only for pre-outcome supply,
   never by looking at Y. Missing decision-time age on any row is
   `REPLAN_POPULATION_DEFINITION`, not a silent UNKNOWN_AGE pass.

## Decision capsule

- `DECISION_DELTA:` Population Fit before Feature Fit. Freeze EARLY/SEASONED
  or stop the branch. Do not start another X atom.
- `UNCERTAINTY_REMOVED:` whether named Git campaigns justify one fresh
  in-scope maturity comparison, with source labels kept distinct from
  product population.
- `CAPABILITY_OR_EVIDENCE:` one thin offline projector + campaign×stratum
  matrix + frozen ATOM 2 contract or explicit STOP. Core capability `NONE`.
- `STOP:` after the decision packet. Exact-head CI then owner merge phrase.
  No provider call. No ATOM 2 in this write set.
- `NEXT:` `NOMINATE_IN_SCOPE_MATURITY_BOUNDARY_TEST` unlocks ATOM 2
  (`IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1`) under a new contract.
  `INSUFFICIENT_COMPARABLE_EVIDENCE` / `STOP_POPULATION_BRANCH` /
  `REPLAN_POPULATION_DEFINITION` forbid ATOM 2.
- `CHEAPEST_FALSIFIER:` pinned receipt hash drift, duplicate derived rows,
  H3600 used as Y, or TRADED treated as product population.
- `REPLAN_TRIGGER:` second preparatory-only atom, population cannot be
  defined PIT-safe, or a request for a fourth X / TRADED pivot.
- `strongest_rejected_alternative:` immediately run a live liquidity/mcap or
  TRADED scout. Rejected: mixed evidence surfaces, control-source confounding.

## PRD

**Problem.** Recent quote-native campaigns mixed `/recent` and `/toptraded`
control sources. Several screens improved only by keeping TRADED and then
closed `STRATUM_UNSTABLE`. `/toptraded` is not a product population. The
open uncertainty is bad X vs bad early population vs source confounding.

**Owner decision unlocked.** Exactly one of:

`NOMINATE_IN_SCOPE_MATURITY_BOUNDARY_TEST`
`STOP_POPULATION_BRANCH`
`INSUFFICIENT_COMPARABLE_EVIDENCE`
`REPLAN_POPULATION_DEFINITION`

**Named consumer.** ATOM 2 `IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1`.

**Question.** Does early-population trouble repeat strongly enough to justify
one prospective `fresh/early pump.fun` vs `seasoned pump.fun` comparison
inside product scope?

**Unit of replication.** Primary = independent capture campaign/window.
Secondary = token within campaign. Do not treat pooled rows as independent.

**Exact evidence set** (no recency search): the six named runtime receipts
pinned in config. Overlay-only: the `#168` MEU reproject. Excluded as market
observations: invalid/429 campaigns, H3600 Y, A24 retrospective, overlays as
new rows, organic/flow/TX_IMBALANCE, retention-clock campaigns not in the pin
list.

**Success (`NOMINATE`)** if all hold:

1. several independent valid capture windows;
2. material source-stratum instability exists;
3. current very-early product geometry is not convincingly positive;
4. `/toptraded` cannot be accepted as the product population;
5. maturity can be defined from pre-outcome fields (`firstPool.createdAt` /
   `age_seconds` at decision time).

**Failure.** Heterogeneous / incomparable Y or notional →
`INSUFFICIENT_COMPARABLE_EVIDENCE`. That is not a data-platform project.

**Non-goals.** Do not prove Seasoned superiority, pick a feature, claim alpha,
change Factory, call a provider, or introduce ML.

**Frozen ATOM 2 population (immutable if NOMINATE):**

- domain: Solana / pump.fun
- EARLY: `5m <= pool_age < 15m`
- SEASONED: `30m <= pool_age <= 120m`
- common: liquidity >= $1000; quote 0.01 SOL; no consumed mint;
  decision-time fields only
- source `/recent` and `/toptraded/1h` may fetch candidates; source does not
  define population

## SSD

**External calls.** provider/API/RPC/WSS = 0; credentials = 0; cash = $0.

**Reuse.** Named runtime receipts, `project_quote` MEU overlay already bound
by `#168`, Catalog, ordinary evidence pattern. Factory `runner.py` must not
change.

**Truth model.** Each source row: source_receipt_sha256, campaign_id,
capture_at, identity_id, mint, source_stratum, population_admissibility,
H900_terminal, Y_if_numeric, time_separated.

**Dedup.** Fail-closed on mint + source receipt + campaign + identity.
A derived overlay row is not a second observation.

**Failure semantics.** MEU ≠ missing; provider failure ≠ MEU; unknown ≠ zero;
`y_equals_x` ≠ honest time-separated Y.

**Output.** One compact packet: matrix → conclusion → frozen ATOM 2 contract
or STOP. No architecture intent, no roadmap, no methodology whitepaper.

**DoD.** Exact input inventory bound; duplicate accounting PASS; no invalid
market receipt; campaign-level table; population frozen or explicit STOP;
zero provider calls; one owner readout; Factory Fit completed.

## Anti-bureaucracy

Do not optimize local-atom completeness over a decision-bearing packet.
Scientific FAIL is a valid terminal. Do not repair FAIL into PASS. A second
preparatory-only substantial step is `REPLAN`, not a suffix atom.
