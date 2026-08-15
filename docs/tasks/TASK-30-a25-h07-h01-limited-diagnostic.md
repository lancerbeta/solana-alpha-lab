---
task_id: TASK-30
task_version: '25.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d982cdf802243558ff9609ddafe8785663e22a9b
  expected_upstream: origin/main
  expected_upstream_oid: d982cdf802243558ff9609ddafe8785663e22a9b
  expected_branch: cursor/task30-a25-h07-h01-limited-diagnostic
  dirty_mode: ALLOW_REPORTED
objective: Decide whether the frozen H07/H01 estimand is measurable on the A24 panel, at what precision, and what exact data scale a decisive test would require.
managed_write_set:
  - docs/tasks/TASK-30-a25-h07-h01-limited-diagnostic.md
  - docs/contracts/task30_a25_h07_h01_limited_diagnostic_contract_v1.md
  - configs/task30_a25_h07_h01_limited_diagnostic_v1.yaml
  - catalog/schemas/task30_a25_h07_h01_limited_diagnostic.schema.json
  - src/solana_alpha_lab/task30_h07_h01_limited_diagnostic.py
  - scripts/run_task30_a25_h07_h01_limited_diagnostic.py
  - tests/fixtures/task30/h07_h01_limited_diagnostic_v1.json
  - tests/test_task30_a25_h07_h01_limited_diagnostic.py
  - docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json
  - docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json
  - docs/reports/task30/a25_h07_h01_limited_diagnostic_owner_readout_v1.md
  - docs/evidence/task30/a25_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a25_delivery_independent_review_v1.json
  - docs/evidence/task30/a25_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - tests/test_lifecycle_registries.py
  - tests/test_catalog.py
  - local/task30_a25_h07_h01_limited_diagnostic/**
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - INPUT_HASH_DRIFT
  - UPSTREAM_PANEL_TERMINAL_DRIFT
  - ORIENTATION_CONSTANT_DRIFT
  - FROZEN_ESTIMAND_OWNER_DISAGREEMENT
  - RESTATED_OR_DRIFTED_ESTIMAND
  - DECLARED_ABSENT_FIELD_PRESENT
  - UNKNOWN_COVERAGE_PRESENT
  - MISSING_TO_ZERO_OR_FLAT_COERCION
  - NAIVE_PRECISION_CLAIM_ON_SINGLE_CLUSTER
  - PROVIDER_OR_CREDENTIAL_CALL_REQUIRED
  - SECOND_PROVIDER_OR_ROUTE_PIVOT
  - PUBLIC_SCHEMA_OR_RC001_MEANING_CHANGE
  - TASK30_OR_RC001_PROMOTION
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONTRACT-T30-H07-H01-DATA-CONTRACT-GATE-001
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - CONTRACT-T30-A24-RAW-TO-PIT-001
    - CONFIG-T30-A24-RAW-TO-PIT-001
    - MODULE-T30-A24-RAW-TO-PIT-001
    - EVIDENCE-T30-A24-RAW-TO-PIT-001
  l2_roles: [DELIVERY_EVIDENCE, ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/decisions/ADR-002-mvp-stack.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json
      - docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json
      - docs/evidence/task30/a25_delivery_completion_evidence_v1.json
      - docs/evidence/task30/a25_delivery_independent_review_v1.json
      - docs/evidence/task30/a25_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A25 — Frozen H07/H01 limited diagnostic and measurability verdict

## Task Outcome Brief

- **Owner decision:** one terminal decision about the fate of the named consumer `RC001-H07-H01-LIQUIDITY-RETENTION`, based on whether its frozen estimand can be computed honestly from the A24 panel.
- **Product outcome:** a measurability verdict, not an effect claim. The atom either kills the hypothesis on this data shape or converts "we need more data" into an exact data specification, before any money is spent on a provider.
- **Named consumers:** `RC001-H07-H01-LIQUIDITY-RETENTION` and the owner's budget decision about buying more data.
- **Cheapest falsifier:** recompute the A24 panel from the retained bytes and attempt the frozen estimand. If the estimand's own data contract cannot be satisfied by the panel shape, the honest outcome is the named capability gap, not a number.
- **Terminal outcomes:** `ESTIMAND_MEASURABLE_AND_DECISIVE_ON_FROZEN_PANEL`, `ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC`, `ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN`, or `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** a machine-readable terminal decision JSON, a concise Russian owner readout, explicit precision and power limits, and an exact required-data specification.
- **Evidence budget:** two already-retained raw inputs, zero external reads, about 20 minutes for the cheapest falsifier and 120 minutes for the full atom.
- **Non-goals:** TASK-30 acceptance or DONE; H07/H01 trial execution; alpha or strategy promotion; PnL, NetReturn or cashflow; prospective PIT route; continuous-price claim by forward-fill; missing-to-zero or missing-to-flat coercion; a second provider; Parquet/DuckDB production integration; UI, deploy, scheduler or background collection.
- **Replan trigger:** input or orientation drift; the two frozen estimand owners disagree; a provider call or credential becomes necessary; a second provider or route is proposed; a forbidden coercion would be needed to produce a number; RC001 meaning must change; the atom exceeds its evidence or time budget.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=WRAP_EXISTING_A24_PANEL_AND_FROZEN_ESTIMAND`

`OWNER_CAPTURE_PHRASE=OK T30-A25 H07_H01_FROZEN_LIMITED_DIAGNOSTIC_AND_MEASURABILITY_VERDICT`

## Frozen mission fields

- **DECISION_DELTA:** whether the owner should fund more data for RC001-H07-H01, retire it, or run a diagnostic on what already exists.
- **UNCERTAINTY_REMOVED:** panel admissibility versus estimand measurability. A24 proved the panel is honest; A25 proves what the frozen estimand can and cannot ask of it.
- **CAPABILITY_OR_EVIDENCE:** a proved lane-field supply map, per-metric computability, declared slot-state consumption, an explicit single-cluster precision statement and an exact required-data specification. No new decoder, provider abstraction or dependency.
- **STOP:** zero provider, credential, network or cash side effects; no TASK-30 or RC001 promotion; no effect estimate; no naive precision on a single cluster; no missing-to-zero, flat or forward-fill.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. The terminal decision then tells the owner whether to fund a variance-calibration capture that adds the named route-feasibility lane, or to retire RC001-H07-H01.

## Managed write set

```
docs/tasks/TASK-30-a25-h07-h01-limited-diagnostic.md
docs/contracts/task30_a25_h07_h01_limited_diagnostic_contract_v1.md
configs/task30_a25_h07_h01_limited_diagnostic_v1.yaml
catalog/schemas/task30_a25_h07_h01_limited_diagnostic.schema.json
src/solana_alpha_lab/task30_h07_h01_limited_diagnostic.py
scripts/run_task30_a25_h07_h01_limited_diagnostic.py
tests/fixtures/task30/h07_h01_limited_diagnostic_v1.json
tests/test_task30_a25_h07_h01_limited_diagnostic.py
docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json
docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json
docs/reports/task30/a25_h07_h01_limited_diagnostic_owner_readout_v1.md
docs/evidence/task30/a25_delivery_completion_evidence_v1.json
docs/evidence/task30/a25_delivery_independent_review_v1.json
docs/evidence/task30/a25_delivery_factory_fit_v1.json
registries/decisions_negative_results.yaml
catalog/catalog_manifest.yaml
catalog/assets/core.yaml
catalog/assets/lifecycle.yaml
catalog/generated/asset_edges.json
docs/PROJECT_MAP.md
tests/test_lifecycle_registries.py
tests/test_catalog.py
local/task30_a25_h07_h01_limited_diagnostic/**
```

## Definition of Done

1. Both frozen estimand owners are read, cross-bound on the in-YAML `definition_sha256`, and any disagreement fails closed. The estimand is never restated.
2. The A24 panel is recomputed through the existing module and the frozen orientation constants are reproduced exactly or the atom stops.
3. Every frozen lane field is classified exactly once; declared absences are proved against the actual panel leaf names.
4. Computability is decided per frozen target metric, justified against exact paths in the frozen entry gate.
5. Statistics declare the slot states they consume; state-persistence slots are never observed trades and carry-forward is never a fresh observation.
6. Precision is reported for the real design: one pool-day is one cluster, the standard error is undefined, and the naive binomial value is emitted only as invalid.
7. An exact required-data specification names the absent fields, the minimum cluster counts and the unresolved frozen parameter, and refuses to invent a decisive sample size.
8. Exactly one terminal decision is produced; `TASK-30` stays `BLOCKED_DATA` and RC001 is not promoted.
9. Code, goal/DoD and architecture review pass; Catalog, generated views, secret and diff checks pass.
10. Exact-head CI passes; merge follows the repository owner-attention policy. Merge is not semantic acceptance.

## Authority and non-claims

The owner authorized this exact offline atom over already-retained bytes.
Provider, credential, purchase, deployment, wallet, signer, transaction,
repository-setting and destructive actions remain forbidden. `TASK-30` remains
`BLOCKED_DATA`. RC001 definition bytes and the A22/A23 retained raw bytes stay
frozen. This atom claims no effect, no trial, no alpha, no PnL and no cashflow.
