---
task_id: FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-23'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CODEX_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0cba257da5240057df4bb8ff91cf3a7f3c0feb9f
  expected_upstream: origin/main
  expected_upstream_oid: 0cba257da5240057df4bb8ff91cf3a7f3c0feb9f
  expected_branch: codex/factory-v1-pit-data-truth-canonicalization
  dirty_mode: ALLOW_REPORTED
objective: Canonicalize the already accepted prospective Atom 1 market truth into the smallest reusable, bounded PIT-ready Factory feature capability without new capture, provider access, scientific re-evaluation, or Factory runner change.
managed_write_set:
- docs/tasks/FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1.md
- configs/factory_v1_common_market_feature_surface_v1.yaml
- catalog/schemas/factory_v1_common_market_feature_surface.schema.json
- catalog/schemas/factory_v1_pit_data_truth_canonicalization.schema.json
- src/solana_alpha_lab/factory/market_feature_surface.py
- src/solana_alpha_lab/factory/pit_data_truth_canonicalization.py
- scripts/run_factory_v1_pit_data_truth_canonicalization.py
- tests/test_factory_v1_pit_data_truth_canonicalization.py
- tests/test_factory_v1_common_market_feature_surface.py
- configs/experiment_specs/market_feature_price_path_archetype_v1.yaml
- configs/experiment_specs/market_feature_liquidity_archetype_v1.yaml
- configs/experiment_specs/market_feature_creator_pressure_archetype_v1.yaml
- configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml
- configs/experiment_specs/ordinary_liquidity_quote_pressure_v1.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_runtime_receipt_v1.json
- docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json
- docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_independent_review_v1.json
- docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_factory_fit_v1.json
- docs/reports/factory_v1_pit_data_truth_canonicalization/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_NETWORK_OR_RPC_CALL
- CREDENTIAL_OR_API_KEY_READ
- NEW_MARKET_CAPTURE_OR_RECAPTURE
- SCIENTIFIC_REEVALUATION_OR_THRESHOLD_SEARCH
- FDV_AS_MCAP_SUBSTITUTE
- UNKNOWN_OR_MISSING_AS_ZERO
- FUTURE_TIMESTAMP_ADMITTED_AT_DECISION
- SEMANTICALLY_CONFLICTING_FEATURE_ID_REUSE
- HISTORICAL_RECEIPT_OR_FEATURE_IDENTITY_REWRITE
- FACTORY_RUNNER_CHANGE
- NEW_PROVIDER_OR_FEATURE_STORE
- SHADOW_VPS_OR_MICRO_LIVE
- ALPHA_NETRETURN_OR_READY_CLAIM
- A5_LIVE_OPS_OR_A6_POLICY_CERTIFICATION
- WALLET_SIGNER_TRANSACTION_OR_CASH
context_requirements:
  catalog_asset_ids:
  - ARCH-INTENT-005
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001
  - CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001
  - EVIDENCE-EARLY-STRUCTURAL-BACKING-PIT-ACCEPTANCE-001
  - EVIDENCE-EARLY-STRUCTURAL-BACKING-PIT-WINDOW-A-001
  - EVIDENCE-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-ACCEPTANCE-001
  - EVIDENCE-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-GATE-001
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
    - docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_delivery_factory_fit_v1.json
    - docs/evidence/factory_v1_common_market_feature_surface/a1_factory_v1_common_market_feature_surface_acceptance_v1.json
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_gate_receipt_v1.json
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1

## Entry Gate

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=REBASE` from the owner-supplied tactical plan after the
merged Atom 3 terminal `FACTORY_PRODUCTIZATION_REPLAN`. This contract executes
only A4; A5 and A6 remain non-authoritative conditional context until their own
exact contracts and boundaries are bound.

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge after the A4 terminal.

The attached tactical document is macro planning context. This Git contract is
the exact bounded execution authority for A4, supplied and authorized by the
owner's direct request.

## Decision capsule

- `DECISION_DELTA`: determine whether accepted prospective Atom 1 data can
  become one reusable, bounded Factory PIT feature without new market capture.
- `UNCERTAINTY_REMOVED`: whether the readiness data gaps are missing capability
  or only missing canonicalization of already-proven evidence.
- `CAPABILITY_OR_EVIDENCE`: one semantically correct PIT-ready feature contract
  and current acceptance proving lineage, typed missingness, timestamp
  admissibility, and first-market-byte economy.
- `STOP`: before provider/network/credential access, recapture, scientific
  promotion, SHADOW/VPS work, false identity reuse, or READY certification.
- `NEXT`: A5 live operational hardening only after an honest A4 PASS; otherwise
  one typed data replan from the evidence defect.
- `REPLAN_TRIGGER`: Atom 1 bytes cannot support reproducible PIT semantics;
  another preparatory-only atom would be needed; a second provider/route is
  proposed; the cheapest falsifier cannot run; or the evidence budget is
  breached.

## PRD-lite

The current common market feature surface still reports `pit_ready_count: 0`,
while the accepted Atom 1 prospective experiment already contains decision-time
`liquidity` and `mcap`, source/observation timestamps, hashes, explicit missing
values, `mcap != fdv`, and rejection of future `updatedAt` values. A4 wraps that
truth into the smallest reusable feature identity and keeps the scientific
family terminal `CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY` unchanged.

### Named consumer

`FACTORY_V1_OPERATIONAL_READINESS_CLOSEOUT` consumes the current acceptance;
future ordinary hypotheses may compose the same bounded decision-time token
state.

### Exact predicates owned

```text
DATA_FACTORY_PIT_LINEAGE_RECEIPT
DATA_EXPLICIT_MISSINGNESS
TIME_TO_EVIDENCE_FIRST_BYTE
```

No other readiness predicate belongs to A4.

### Semantic target

```text
concept: token liquidity USD / token market cap USD
entity_scope: MINT_DECISION_SNAPSHOT
units: ratio
availability: PIT_READY only inside the proven acquisition scope
suggested_id: FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO
```

Do not reuse `FEAT-MCAP-TO-LIQUIDITY` unless exact semantic equivalence is
independently demonstrated. The fresh experiment is the inverse ratio and has
different prior entity and availability semantics.

## SSD-lite

`ADOPT` the frozen Atom 1 runtime evidence, current typed PIT/missingness
semantics, feature-surface vocabulary and Catalog lineage mechanisms.

`WRAP` the accepted decision-time observation into a reusable projection.

`BUILD` only a narrow projector/schema/test if existing code cannot express the
semantics. `FORK=NONE`.

### Cheapest falsifier, before Catalog ceremony

1. Parse the frozen Atom 1 acceptance and runtime receipt.
2. Reproduce the candidate ratio from accepted rows only.
3. Prove each admitted value was available at or before decision time.
4. Prove typed missingness for missing, invalid, future, and lineage-defective
   rows; `fdv` never substitutes for `mcap`.
5. Prove the proposed feature identity is not semantically conflicting.
6. Prove historical Atom 1 and old feature-surface receipts remain unchanged.
7. Prove the Factory runner SHA remains unchanged and no network/credential
   path is reachable.

If any falsifier fails, stop before adding a new reusable record and return the
typed terminal `PIT_CANONICALIZATION_EVIDENCE_INSUFFICIENT`,
`FEATURE_IDENTITY_CONFLICT`, or `PIT_LINEAGE_NOT_REPRODUCIBLE` as applicable.

### Required acceptance fields

```yaml
terminal: FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_PASS
readiness:
  pit_lineage_ready: true
  explicit_missingness_preserved: true
  first_market_byte_within_one_preparatory_step: true
feature:
  feature_id: FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO
  availability_class: PIT_READY
  availability_scope: <exact proven scope>
scientific_family:
  family: EARLY_STRUCTURAL_BACKING
  terminal: CLOSED
  reopened: false
factory_runner_changed: false
provider_calls: 0
credential_reads: 0
```

`PIT_READY` is scoped to the proven Tokens V2 decision-snapshot route,
explicit `decision_snapshot_at`, field availability checks, and proven
acquisition timing. It is not a global claim about every provider, population,
time horizon, or future schema.

### Validation and delivery

Zero-network deterministic tests must cover computation, identity,
timestamp admissibility, typed missingness, replay from pinned evidence,
scientific-family closure, historical receipt immutability, runner SHA, and
absence of provider/credential access. Generated Catalog consumers are routine
propagation and must not be hand-edited.

The terminal claim after PASS is only: the current Factory has at least one
bounded reusable PIT-ready feature capability with explicit missingness and
proven fast first market byte. It is not `FACTORY_V1_OPERATIONAL_READY`,
alpha, NetReturn, scientific SHADOW, or micro-live.

## Owner and external boundary

This contract permits local repository writes, zero-network tests, ordinary
commit/PR/review transport and the Delivery Harness merge process within this
write set. It grants no provider/API/RPC/WSS, credential, deployment, purchase,
wallet/signer/transaction, real-money, A5 live-host, or A6 certification
authority. A5 and A6 require separate exact contracts.
