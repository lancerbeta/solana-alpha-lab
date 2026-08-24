---
task_id: EARLY_HOLDER_CONCENTRATION_ACTIONABILITY_RULE_OOS_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6d5a7e1cbddb5875ae16f2125c5f3f7a3faed3bd
  expected_upstream: origin/main
  expected_upstream_oid: 6d5a7e1cbddb5875ae16f2125c5f3f7a3faed3bd
  expected_branch: cursor/early-holder-concentration-actionability-rule-oos
  dirty_mode: ALLOW_REPORTED
objective: "Adjudicate whether the replicated holder-concentration relation supports one frozen top-quartile veto as a decision rule; Phase A offline only, then one fresh rule-OOS if it survives."
managed_write_set:
- docs/tasks/EARLY_HOLDER_CONCENTRATION_ACTIONABILITY_RULE_OOS_V1.md
- configs/early_holder_concentration_actionability_rule_oos_v1.yaml
- src/solana_alpha_lab/holder_concentration_top_quartile_veto.py
- scripts/run_holder_concentration_top_quartile_veto_phase_a.py
- tests/test_holder_concentration_top_quartile_veto.py
- docs/evidence/early_holder_concentration_actionability_rule_oos/a1_phase_a_receipt_v1.json
- docs/reports/early_holder_concentration_actionability_rule_oos/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_BEFORE_PHASE_A_SURVIVAL
- THRESHOLD_PERCENTILE_OR_K_SEARCH
- ABSOLUTE_X_CUTOFF
- MEDIAN_SPLIT_OR_TERCILE
- POOLED_QUARTILE_RECOMPUTE
- USE_OF_189_OR_OTHER_FAMILY_Y
- IMPUTE_Y_FOR_MARKET_EXECUTION_UNAVAILABLE
- CAMPAIGN_ORCHESTRATION_DELTA
- X_PROJECTOR_OR_KENDALL_RUNTIME_CHANGE
- FACTORY_RUNNER_CHANGE
- SECOND_PROVIDER
- STRATEGY_BOT_SHADOW_ALPHA_OR_NETRETURN
- PREPARATORY_ONLY_READY_FOR_LIVE_PR
- AUTOMATIC_THIRD_MECHANISM_SAMPLE
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-FALSIFIER-001
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-OOS-001
  - EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-RUNTIME-001
  - EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-RUNTIME-001
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json
    - docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_HOLDER_CONCENTRATION_ACTIONABILITY_RULE_OOS_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` — PIT/statistical decision-utility
adjudication. `NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` if Phase A fails;
`ROUTINE_NO_SWITCH` at a later live-phrase checkpoint if it survives.

`ROADMAP_VERDICT=KEEP`

Owner-selected after PR 191 merge + post-merge read-back + main CI PASS.
Do not hunt a new mechanism. Do not take a third sign-only sample.

## Atom identity

```text
DECISION_DELTA: freeze HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1 as a
  decision-utility hypothesis after mechanism replication
UNCERTAINTY_REMOVED: whether that frozen veto has enough development-set
  decision utility to deserve one fresh rule-OOS window
CAPABILITY_OR_EVIDENCE: Phase A typed terminal, or one later rule-OOS
  terminal if Phase A survives
STOP: no Jupiter until Phase A survival + exact owner phrase; no rule search
NEXT: REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO |
  INVALID_EVIDENCE_REPLAN |
  CLOSE_HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_RULE |
  EARN_PAPER_HOLDER_CONCENTRATION_TOP_QUARTILE_VETO
REPLAN_TRIGGER: any change to veto percentile/K; absolute X cutoff;
  campaign/X/Kendall/H900 runtime change; preparatory-only PR
```

## Frozen action rule

`RULE_ID=HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1`

Bound before row-level development Y is inspected.

1. Ordinary `ICP-EARLY-PUMPFUN-V1` decision cohort.
2. `X = audit.topHoldersPercentage`.
3. Missing/invalid X → `VETO_UNKNOWN` / no entry.
4. Among X-valid decision-time eligible rows, sort by X descending, then mint
   lexical order.
5. `veto_count = ceil(valid_x_eligible_count / 4)`.
6. Highest-concentration `veto_count` → `VETO_HIGH_X`.
7. Remainder → `PASS`.

No absolute X threshold. No median/tercile/K/percentile search.
Labels are assigned **per window**. Pooled metrics reuse those labels; they
must not recompute the quartile on the pooled sample.

Limitation: `jupiter_top_holders_pool_exclusion = UNKNOWN`.

## Phase A development evidence

Only:

- `docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json`
- `docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_runtime_receipt_v1.json`

No network. No #189 Y. No other family.

These two windows become DESIGN/DEVELOPMENT evidence once row-level Y is
opened. They are not future validation for this rule.

## Frozen metrics

`operational_bad` =
`h900_terminal == MARKET_EXECUTION_UNAVAILABLE`
OR
(`h900_terminal == QUOTE_OBSERVED` and numeric `Y < 0`).

Do not impute numeric Y for MARKET_EXECUTION_UNAVAILABLE.

Median Y is computed only on rankable quote-observed numeric Y.
Mean Y and P25 Y are diagnostics only.

## Phase A survival (all required)

A. In BOTH windows:
`median_Y_PASS > median_Y_VETO_HIGH_X`
AND
`median_Y_PASS > median_Y_ALL_RANKABLE`

B. Pooled development:
`median_Y_PASS > 0`

C. In BOTH windows:
`operational_bad_rate_PASS < operational_bad_rate_ALL_X_VALID`

D. In BOTH windows:
PASS decision-time count >= 12

If any fail:

`REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO`

No Jupiter. No alternative rule. Mechanism remains REPLICATED.

## Factory leverage

Phase A: small offline scorer over `{mint, x, x_status, h900_terminal, y}` only.
No campaign/H900/provider/X-projector/Kendall/runtime change.

If Phase A survives, reuse the existing holder campaign for one fresh window.
`NEW_CAMPAIGN_ORCHESTRATION_LOC = 0`.

## DoD terminals

Exactly one of:

- `REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO`
- `INVALID_EVIDENCE_REPLAN`
- `CLOSE_HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_RULE`
- `EARN_PAPER_HOLDER_CONCENTRATION_TOP_QUARTILE_VETO`

`READY_FOR_LIVE` is not DONE.
